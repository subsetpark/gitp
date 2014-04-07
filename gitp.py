import subprocess, sublime, sublime_plugin
from collections import defaultdict

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
    registers[id(view)] = {'active': defaultdict(),
                           'staged': defaultdict()}

def plugin_loaded():
    for window in sublime.windows():
        for view in window.views():
            print("loading register: ", view.file_name())
            load_registers(view)

def id(view):
    return view.buffer_id()

def dirname(view):
    filename = view.file_name()
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

def cli(view, view_type):
    filename = view.file_name()
    command = ['git', 'diff']
    if view_type == 'staged':
        command.append('--cached')
    if is_prose(view):
        command.append('--unified=1')
    command.append(filename)
    return command

def check_output(command, view):
    return subprocess.check_output(command,
                                    stderr=subprocess.STDOUT,
                                    cwd=dirname(view)).decode('UTF-8')

def gen_diff(view, view_type='active'):
    if view.file_name():
        return check_output(cli(view, view_type), view)

def popen(command, view):
    return subprocess.Popen(command,
                         cwd=dirname(view),
                         stderr=subprocess.PIPE,
                         stdin=subprocess.PIPE)

def analyze_diff(diff):
    """
    Analyze a diff file for unidiff content.
    """
    hunk_metadata = [line.split()[2]
                     for line in diff.splitlines() if line.startswith('@@')]
    return [int(word.split(',')[0].translate({ord(i) : None for i in '-+,'}))
            for word in hunk_metadata]

def erase_hunks(view, key):
    for k in registers[id(view)][key].keys():
        view.erase_regions(k)
    registers[id(view)][key].clear()

def paint_hunks(view, key):
    erase_hunks(view, key)
    hunk_line_nos = analyze_diff(gen_diff(view, key))
    pts = []
    modifier = 1 if is_prose(view) else 2
    if hunk_line_nos:
        pts = [sublime.Region(view.text_point(l + modifier, 0))
               for l in hunk_line_nos]
        if pts:
            for i, pt in enumerate(pts):
                if key == "active":
                    digit = DIGITS[i] if i < len(DIGITS) else 'bookmark'
                elif key == "staged":
                    digit = "dot"
                keyname = key + str(i)
                view.add_regions(keyname, [pt], "gitp", digit,
                                 sublime.DRAW_NO_FILL | sublime.PERSISTENT)
                r = view.get_regions(keyname)[0]
                registers[id(view)][key][keyname] = r

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
    diff = gen_diff(view)
    hunk_line_nos = analyze_diff(diff)
    last_line = diff.splitlines()[-1]
    final_line = last_line if last_line.startswith('\\') else False

    new_diff = select_diff_portions(diff, h_to_stage)
    if final_line and new_diff.splitlines()[-1] != final_line:
        new_diff += ("\n" + final_line)
    new_diff = (new_diff.rstrip(' '))
    if not new_diff.endswith("\n"):
        new_diff += "\n"

    p = popen(['git', 'apply', '--cached', '--recount', '--allow-overlap'],
              view)

    print("git staging response: ",
          p.communicate(input=new_diff.encode('UTF-8')))
    view.run_command('display_hunks')

def unstage_hunks(view, choices):
    #first we'll unstage everything, then restage without the choices.
    filename = view.file_name()
    unstage_cli = ['git', 'reset', 'HEAD', filename]
    print("unstaging response: ", check_output(unstage_cli, view))
    view.run_command('display_hunks')

def select_hunks_of_type(view, view_type):
        hunks_to_view = [hunk for hunk, region in 
                         registers[id(view)][view_type].items()
                         if view.sel().contains(region)]
        selected_hunk_labels = get_hunk_ints(hunks_to_view)
        return selected_hunk_labels

class EditDiffCommand(sublime_plugin.TextCommand):
    def crunch_diff(self, str):
        choices = [int(char) for char in str if char.isdigit()]
        stage_hunks(self.view, choices)

    def run(self, edit):
        self.view.window().show_input_panel('Please enter choices: ',
                                            '', self.crunch_diff, None, None)

class CommitHunks(sublime_plugin.TextCommand):
    def commit_patch(self, str):
        p = popen(['git', 'commit', '--file=-'], self.view)
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
            print("active hunks in {}: {}"
                 .format(filename.split("/")[-1], 
                         registers[id(self.view)]['active']))
            print("staged hunks in {}: {}"
                 .format(filename.split("/")[-1],
                         registers[id(self.view)]['staged']))
            paint_hunks(self.view, 'active')
            paint_hunks(self.view, 'staged')

class ViewHunksCommand(sublime_plugin.TextCommand):
    """
    When a line with a hunk icon is selected and this command is run,
    it will open a window with that hunk displayed.
    """
    def run(self, edit):
        expand_sel(self.view)
        print("active hunks: ", registers[id(self.view)]['active'])
        print("staged hunks: ", registers[id(self.view)]['staged'])
        print("selection: ", list(self.view.sel()))

        selected = select_hunks_of_type(self.view, 'active')
        diff_type = 'active'
        title = "Hunk"

        if not selected:
            selected = select_hunks_of_type(self.view, 'staged')
            diff_type = 'staged'
            title = "Staged"

        if not selected:
            return

        diff = check_output(cli(self.view, diff_type), self.view)
        print("diff: ", diff)
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
        hunks_to_stage = select_hunks_of_type(self.view, 'active')
        if hunks_to_stage:
            stage_hunks(self.view, hunks_to_stage)

class UnstageTheseHunks(sublime_plugin.TextCommand):
    """
    The opposite of above.
    """
    def run(self, edit):
        expand_sel(self.view)
        hunks_to_unstage =  select_hunks_of_type(self.view, 'staged')
        print('*' * 10)
        print("hunks to unstage: ", hunks_to_unstage)
        print("unstage choices: ", hunks_to_unstage)
        if hunks_to_unstage:
            unstage_hunks(self.view, hunks_to_unstage)
        staged_hunk_ints = set(get_hunk_ints(
                              registers[id(self.view)]['staged'].keys()))
        stage_choices =  staged_hunk_ints - set(hunks_to_unstage)
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
        if not registers.get(id(view)):
          load_registers(view)
        view.run_command("display_hunks")

    def on_load(self, view):
        if not registers.get(id(view)):
          load_registers(view)

    def on_activated(self, view):
        view.run_command("display_hunks")