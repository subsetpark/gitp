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

def gen_diff(view):
    if view.file_name():
        return subprocess.check_output(diff_cli(view), 
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
        for i in range(len(DIGITS)):
            view.erase_regions('gitp_hunks'+ str(i))
    else:
        view.erase_regions(key)

def paint_hunks(view, key, hunk_line_nos=None):
    erase_hunks(view, key)
    if not hunk_line_nos:
        _, hunk_line_nos = analyze_diff(gen_diff(view))
    pts = []
    modifier = 1 if is_prose(view) else 2
    if hunk_line_nos: 
        pts = [sublime.Region(view.text_point(l + modifier, 0)) 
               for l in hunk_line_nos]
        if key is "hunks":
            # We treat these specially in order to get custom icons.
            for i, pt in enumerate(pts):
                keyname = 'gitp_hunks'+str(i)
                digit = DIGITS[i] if i < len(DIGITS) else 'bookmark'
                view.add_regions(keyname, 
                                 [pt], 
                                 keyname, 
                                 digit, 
                                 sublime.DRAW_NO_FILL | sublime.PERSISTENT)
                active_hunks[keyname] = view.get_regions(keyname)[0]
        else:
            view.add_regions(key,
                             pts, 
                             key, 
                             ICONS[key], 
                             sublime.HIDDEN | sublime.PERSISTENT)

def expand_sel(view):
    for r in view.sel():
        # adjust selections back to beginning of line
        l, c = view.rowcol(r.begin())
        view.sel().add(sublime.Region(view.text_point(l, 0), 
                                      view.text_point(l, c)))

def stage_hunks(view, choices):
    h_to_stage = [0] + choices 
    filename = view.file_name()

    diff, hunk_line_nos = analyze_diff(gen_diff(view))
    last_line = diff.splitlines()[-1]
    final_line = last_line if last_line.startswith('\\') else False

    new_diff = "\n".join("\n".join(hunk) 
                         for i, hunk in enumerate(chunk(lines(diff))) 
                         if i in h_to_stage)
    if final_line and new_diff.splitlines()[-1] != final_line:
        new_diff += ("\n" + final_line)
    new_diff = (new_diff.rstrip(' '))
    if not new_diff.endswith("\n"):
        new_diff += "\n"
    
    diff_cli = ['git', 'apply', '--cached', '--recount', '--allow-overlap']
    p = subprocess.Popen(diff_cli, 
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
        if filename:
            paint_hunks(self.view, 'hunks')

            if is_prose(self.view):
                stage_cli =  ['git', 'diff', '--cached', '--unified=1', 
                              filename]
            else:
                stage_cli =  ['git', 'diff', '--cached', 
                              filename]
            stage_diff = subprocess.check_output(stage_cli, 
                                                 cwd=dirname(self.view), 
                                                 stderr=subprocess.PIPE)
            if stage_diff:
                stage_diff = stage_diff.decode('UTF-8')
                _, stage_lines = analyze_diff(stage_diff)
                paint_hunks(self.view, 'staged', hunk_line_nos=stage_lines)
            else:
                erase_hunks(self.view, 'staged')

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
        choices = [int("".join(char 
                       for char in name 
                       if char.isdigit())) + 1 for name in hunks_to_view]
        if choices:
            diff = gen_diff(self.view)
            new_diff = "\n".join("\n".join(hunk) 
                                 for i, hunk in enumerate(chunk(lines(diff))) 
                                 if i in choices)
            ndw = self.view.window().new_file()
            ndw.set_scratch(True)
            ndw.set_name('*gitp Hunk View: {}*'
                         .format(self.view.file_name().split("/")[-1]))
            ndw.run_command('new_diff', {'nd': new_diff})

class StageTheseHunksCommand(sublime_plugin.TextCommand):
    """
    Stages currently selected hunks
    """
    def run(self, edit):
        expand_sel(self.view)
        hunks_to_view = [hunk
                        for hunk, region in active_hunks.items() 
                        if self.view.sel().contains(region)]
        choices = [int("".join(char 
                       for char in name 
                       if char.isdigit())) + 1 
                       for name in hunks_to_view]
        if choices:
            stage_hunks(self.view, choices)

class UnstageTheseHunks(sublime_plugin.TextCommand):
    """
    The opposite of above.
    """
    def run(self, edit):
        pass

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
