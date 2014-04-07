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

registers = {}

def load_registers(view):
    registers[view.buffer_id()] = { 'active_hunks': {},
                        'staged_hunks': {}
                        }

def plugin_loaded():
    for window in sublime.windows():
        for view in window.views():
            print("loading register: ", view.file_name())
            load_registers(view)

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
        for k in registers[view.buffer_id()].get('active_hunks').keys():
            view.erase_regions(k)
        registers[view.buffer_id()].get('active_hunks').clear()
    elif key == "staged":
        for k in registers[view.buffer_id()].get('staged_hunks').keys():
            view.erase_regions(k)
        registers[view.buffer_id()].get('staged_hunks').clear()

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
                registers[view.buffer_id()].get('active_hunks')[keyname] = view.get_regions(keyname)[0]
        elif key == "staged" and pts:
            for i, pt in enumerate(pts):
                keyname = 'staged_hunks'+str(i)
                view.add_regions(keyname,
                                 [pt], 
                                 "gitp", 
                                 ICONS[key], 
                                 sublime.HIDDEN | sublime.PERSISTENT)
                registers[view.buffer_id()].get('staged_hunks')[keyname] = view.get_regions(keyname)[0]

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

def unstage_hunks(view, choices):
    #first we'll unstage everything, then restage without the choices.
    filename = view.file_name()
    unstage_cli = ['git', 'reset', 'HEAD', filename]
    print("unstaging response: ", 
                            subprocess.check_output(unstage_cli,
                            cwd= dirname(view),
                            stderr=subprocess.PIPE))
    view.run_command('display_hunks')

class EditDiffCommand(sublime_plugin.TextCommand):
    def crunch_diff(self, str):
        choices = [int(char) for char in str if char.isdigit()]
        stage_hunks(self.view, choices)
            
    def run(self, edit):
        self.view.window().show_input_panel('Please enter choices: ', 
                                            '', self.crunch_diff, None, None)
# trivial change
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
            print("active hunks in {}: {}".format(filename.split("/")[-1], registers[self.view.buffer_id()].get('active_hunks')))
            print("staged hunks in {}: {}".format(filename.split("/")[-1], registers[self.view.buffer_id()].get('staged_hunks')))
            paint_hunks(self.view, 'hunks')
            paint_hunks(self.view, 'staged')

class ViewHunksCommand(sublime_plugin.TextCommand):
    """
    When a line with a hunk icon is selected and this command is run,
    it will open a window with that hunk displayed.
    """
    def select_hunks_of_type(self, view_type):
        hunks_to_view = [hunk
                        for hunk, region in registers[self.view.buffer_id()].get(view_type+'_hunks').items()
                        if self.view.sel().contains(region)]
        selected_hunk_labels = get_hunk_ints(hunks_to_view)
        return selected_hunk_labels

    def run(self, edit):
        expand_sel(self.view)

        print("active hunks: ", registers[self.view.buffer_id()].get('active_hunks'))
        print("staged hunks: ", registers[self.view.buffer_id()].get('staged_hunks'))
        print("selection: ", list(self.view.sel()))

        selected = self.select_hunks_of_type('active')
        gen_cli = gen_diff
        title = "Hunk"

        if not selected:
            selected = self.select_hunks_of_type('staged')
            gen_cli = gen_staged
            title = "Staged"

        if not selected:
            return

        diff = gen_cli(self.view)
        new_diff = select_diff_portions(diff, selected)
        ndw = self.view.window().new_file()
        ndw.set_scratch(True)

        win_name = '*gitp {} View: {}*'.format(title, self.view.file_name()
                                                     .split("/")[-1])
        ndw.set_name(win_name)
        ndw.run_command('new_diff', {'nd': new_diff})

class StageTheseHunksCommand(sublime_plugin.TextCommand):
    """
    Stages currently selected hunks
    """
    def run(self, edit):
        expand_sel(self.view)
        # three
        # line
        # change
        hunks_to_stage = [hunk
                        for hunk, region in registers[self.view.buffer_id()].get('active_hunks').items()
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
                        for hunk, region in registers[self.view.buffer_id()].get('staged_hunks').items() 
                        if self.view.sel().contains(region)]
        print('*' * 10)
        print("hunks to unstage: ", hunks_to_unstage)
        choices = get_hunk_ints(hunks_to_unstage)
        print("unstage choices: ",choices)
        if choices:
            unstage_hunks(self.view, choices)
        stage_choices = set(get_hunk_ints(registers[self.view.buffer_id()].get('staged_hunks').keys())) - set(choices)
        print("staging choices: ", stage_choices)
        # stage_hunks(self.view, stage_choices)
        self.view.run_command('display_hunks')

class NewDiffCommand(sublime_plugin.TextCommand):
    def run(self, edit, nd=None):
        self.view.set_syntax_file('Packages/Diff/Diff.tmLanguage')
        self.view.insert(edit, 0, nd)
        self.view.set_read_only(True)

class HunkListener(sublime_plugin.EventListener):
    def on_post_save(self, view):
        if not registers.get(view.buffer_id()):
          load_registers(view)
        view.run_command("display_hunks")

    def on_load(self, view):
        if not registers.get(view.buffer_id()):
          load_registers(view)
          
    def on_activated(self, view):
        view.run_command("display_hunks")

    # def on_new(self, view):
    #     load_registers(view)