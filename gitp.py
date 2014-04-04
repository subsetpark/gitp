import subprocess, sublime, sublime_plugin

ICONS = { 'hunks': 'bookmark',
          'staged': 'dot'
          }
DIGITS = ['Packages/gitp/icons/1.png',
         'Packages/gitp/icons/2.png',
         'Packages/gitp/icons/3.png',
         'Packages/gitp/icons/4.png',
         'Packages/gitp/icons/5.png',
         'Packages/gitp/icons/6.png',
         'Packages/gitp/icons/7.png',
         'Packages/gitp/icons/8.png',
         'Packages/gitp/icons/9.png'
         ]

active_hunks = {}
staged_hunks = {}

def dirname(view):
    filename = view.file_name()
    if not filename:
        return ""
    return filename[:filename.rfind('/')]

def lines(s):
    for line in s.split('\n'):
        yield line

def chunk(lines):
    chunk = []
    for line in lines:
        if line.startswith('@@'):
            '\n'.join(chunk)
            yield chunk
            chunk = [line]
        else:
            chunk.append(line)
    yield chunk

def is_prose(view):
    return any(view.settings().get('syntax').count(lang) 
           for lang in ('Markdown', 'Plain Text'))
    
def diff_cli(view):
    filename = view.file_name()
    if is_prose(view):
        return ['git', 'diff', '--unified=1', filename]
    else:
        return ['git', 'diff', filename]

def staged_cli(view):
    filename = view.file_name()
    if is_prose(view):
        return ['git', 'diff', '--cached', '--unified=1', filename]
    else:
        return ['git', 'diff', '--cached', filename]

def gen_diff(view):
    if view.file_name():
        return subprocess.check_output(diff_cli(view), 
                                       stderr=subprocess.STDOUT, 
                                       cwd=dirname(view)).decode('UTF-8')
    else:
        return None

def gen_staged(view):
    if view.file_name():
        return subprocess.check_output(staged_cli(view), 
                                       stderr=subprocess.STDOUT, 
                                       cwd=dirname(view)).decode('UTF-8')
    else:
        return None

def analyze_diff(diff):
    """
    Analyze a diff file for unidiff content.
    """
    diff_lines = diff.splitlines()
    hunk_metadata = [line.split()[2] 
                     for line in diff_lines if line.startswith('@@')]
    hunk_line_nos = [int(word.split(',')[0].translate({ord(i) : None 
                     for i in '-+,'})) 
                     for word in hunk_metadata]
    return diff, hunk_line_nos

def erase_hunks(view, key):
    if key == "hunks":
        for k in active_hunks.keys():
            view.erase_regions(k)
    elif key == "staged":
        for k in staged_hunks.keys():
            view.erase_regions(k)

def paint_hunks(view, key):
    erase_hunks(view, key)
    if key == "hunks":
        _, hunk_line_nos = analyze_diff(gen_diff(view))
    elif key == "staged":
        _, hunk_line_nos = analyze_diff(gen_staged(view))
    pts = []
    modifier = 1 if is_prose(view) else 2
    if hunk_line_nos: 
        pts = [sublime.Region(view.text_point(l + modifier, 0)) 
               for l in hunk_line_nos]
        if key is "hunks" and pts:
            # We treat these specially in order to get custom icons.
            for i, pt in enumerate(pts):
                keyname = 'gitp_hunks'+str(i)
                digit = DIGITS[i] if i < len(DIGITS) else 'bookmark'
                view.add_regions(keyname, 
                                 [pt], 
                                 "gitp", 
                                 digit, 
                                 sublime.DRAW_NO_FILL | sublime.PERSISTENT)
                active_hunks[keyname] = view.get_regions(keyname)[0]
        elif key == "staged" and pts:
            for i, pt in enumerate(pts):
                keyname = 'staged_hunks'+str(i)
                view.add_regions(keyname,
                                 [pt], 
                                 "gitp", 
                                 ICONS[key], 
                                 sublime.HIDDEN | sublime.PERSISTENT)
                staged_hunks[keyname] = view.get_regions(keyname)[0]

def expand_sel(view):
    for r in view.sel():
        l, c = view.rowcol(r.begin())
        view.sel().add(sublime.Region(view.text_point(l, 0), 
                                      view.text_point(l, c)))

def get_hunk_ints(regions):
    return [int("".join(char 
                       for char in name 
                       if char.isdigit())) + 1 for name in regions]    

def select_diff_portions(diff, choices):
  return "\n".join("\n".join(hunk) for i, hunk in enumerate(chunk(lines(diff))) 
                                   if i in choices)

def stage_hunks(view, choices):
    h_to_stage = [0] + choices 
    filename = view.file_name()

    diff, hunk_line_nos = analyze_diff(gen_diff(view))
    last_line = diff.splitlines()[-1]
    final_line = last_line if last_line.startswith('\\') else False

    new_diff = select_diff_portions(diff, h_to_stage)
    if final_line and new_diff.splitlines()[-1] != final_line:
        new_diff += ("\n" + final_line)
    new_diff = (new_diff.rstrip(' '))
    if not new_diff.endswith("\n"):
        new_diff += "\n"
    
    apply_cli = ['git', 'apply', '--cached', '--recount', '--allow-overlap']
    p = subprocess.Popen(apply_cli, 
                         cwd=dirname(view), 
                         stderr=subprocess.PIPE, 
                         stdin=subprocess.PIPE)
    print("git staging response: ", 
          p.communicate(input=new_diff.encode('UTF-8')))
    view.run_command('display_hunks')

class EditDiffCommand(sublime_plugin.TextCommand):
    def crunch_diff(self, str):
        choices = [int(char) for char in str if char.isdigit()]
        stage_hunks(self.view, choices)
            
    def run(self, edit):
        self.view.window().show_input_panel('Please enter choices: ', 
                                            '', self.crunch_diff, None, None)

class CommitHunks(sublime_plugin.TextCommand):
    def commit_patch(self, str):
        p = subprocess.Popen(['git', 'commit', '--file=-'],
                             stderr=subprocess.STDOUT, stdin=subprocess.PIPE, 
                             cwd=dirname(self.view))
        print("git commit response: ", 
              p.communicate(input=str.encode('utf-8')))
        erase_hunks(self.view, 'staged')

    def run(self, edit):
        self.view.window().show_input_panel('Please enter a commit message: ', 
                                            '', self.commit_patch, None, None)

class DisplayHunksCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        filename = self.view.file_name()
        print(active_hunks)
        print(staged_hunks)
        if filename:
            paint_hunks(self.view, 'hunks')
            paint_hunks(self.view, 'staged')
            
class ViewHunksCommand(sublime_plugin.TextCommand):
    """
    When a line with a hunk icon is selected and this command is run, 
    it will open a window with that hunk displayed.
    """
    def run(self, edit):
        expand_sel(self.view)
        hunks_to_view = [hunk 
                        for hunk, region in active_hunks.items() 
                        if self.view.sel().contains(region)]
        choices = get_hunk_ints(hunks_to_view)
        gen_cli = False
        print("active hunks: ", active_hunks)
        print("staged hunks: ", staged_hunks)
        print("selection: ", list(self.view.sel()))
        print("choices: ", choices)
        if choices:
          gen_cli = gen_diff
          win_name = '*gitp Hunk View: {}*'.format(self.view.file_name()
                                                   .split("/")[-1])
        else:
          hunks_to_view = [hunk 
                          for hunk, region in staged_hunks.items() 
                          if self.view.sel().contains(region)]
          choices = get_hunk_ints(hunks_to_view)
          if choices:
            gen_cli = gen_staged
            win_name = '*gitp Staged View: {}*'.format(self.view.file_name()
                                                       .split("/")[-1])
        
        if gen_cli:
          diff = gen_cli(self.view)
          new_diff = select_diff_portions(diff, choices)
          ndw = self.view.window().new_file()
          ndw.set_scratch(True)
          ndw.set_name(win_name)
          ndw.run_command('new_diff', {'nd': new_diff})




class StageTheseHunksCommand(sublime_plugin.TextCommand):
    """
    Stages currently selected hunks
    """
    def run(self, edit):
        expand_sel(self.view)
        hunks_to_stage = [hunk
                        for hunk, region in active_hunks.items() 
                        if self.view.sel().contains(region)]
        choices = get_hunk_ints(hunks_to_stage)
        if choices:
            stage_hunks(self.view, choices)

class UnstageTheseHunks(sublime_plugin.TextCommand):
    """
    The opposite of above.
    """
    def run(self, edit):
        expand_sel(self.view)
        hunks_to_unstage = [hunk 
                        for hunk, region in staged_hunks.items() 
                        if self.view.sel().contains(region)]
        print("hunks to unstage: ", hunks_to_unstage)
        choices = get_hunk_ints(hunks_to_unstage)
        print(choices)
        if choices:
            unstage_hunks(self.view, choices)
        

class NewDiffCommand(sublime_plugin.TextCommand):
    def run(self, edit, nd=None):
        self.view.set_syntax_file('Packages/Diff/Diff.tmLanguage')
        self.view.insert(edit, 0, nd)
        self.view.set_read_only(True)

class HunkListener(sublime_plugin.EventListener):
    def on_post_save(self, view):
        view.run_command("display_hunks")

    def on_activated(self, view):
        view.run_command("display_hunks")
