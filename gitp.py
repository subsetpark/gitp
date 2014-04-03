import subprocess, sublime, sublime_plugin

ICONS = { 'hunks': 'bookmark',
          'staged': 'dot'
          }
DIGITS = ['Packages/gitp/icons/1.png'
         ,'Packages/gitp/icons/2.png'
         ,'Packages/gitp/icons/3.png'
         ,'Packages/gitp/icons/4.png'
         ,'Packages/gitp/icons/5.png'
         ,'Packages/gitp/icons/6.png'
         ,'Packages/gitp/icons/7.png'
         ,'Packages/gitp/icons/8.png'
         ,'Packages/gitp/icons/9.png'
         ]

active_hunks = {}

def dirname(view):
    filename = view.file_name()
    if not filename:
        return ""
    return filename[:filename.rfind('/')]

def cur_view():
    return sublime.active_window().active_view()

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
    return any(view.settings().get('syntax').count(lang) for lang in ('Markdown', 'Plain Text'))

def diff_cli(view):
    filename = view.file_name()
    if is_prose(view):
        return ['git', 'diff', '--unified=1', filename]
    else:
        return ['git', 'diff', filename]

def gen_diff(view):
    if view.file_name():
        return subprocess.check_output(diff_cli(view), stderr=subprocess.STDOUT, cwd=dirname(cur_view())).decode('UTF-8')
    else:
        return None

def analyze_diff(diff):
    """
    Analyze a diff file for unidiff content.
    """
    diff_lines = diff.splitlines()
    hunk_metadata = [line.split()[2] for line in diff_lines if line.startswith('@@')]
    hunk_line_nos = [int(word.split(',')[0].translate({ord(i) : None for i in '-+,'})) for word in hunk_metadata]
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
        pts = [sublime.Region(view.text_point(l + modifier, 0)) for l in hunk_line_nos]
        if key is "hunks":
            for i, pt in enumerate(pts):
                keyname = 'gitp_hunks'+str(i)
                digit = DIGITS[i] if i < len(DIGITS) else 'bookmark'
                view.add_regions(keyname, [pt], keyname, digit, sublime.DRAW_NO_FILL | sublime.PERSISTENT)
                active_hunks[keyname] = view.get_regions(keyname)[0]
        else:
            print("adding regions with key", key)
            view.add_regions(key, pts, key, ICONS[key], sublime.HIDDEN | sublime.PERSISTENT)
        print("active hunks: ",active_hunks)         

class EditDiffCommand(sublime_plugin.WindowCommand):
    def crunch_diff(self, str):
        active_hunks = [int(char) for char in str if char.isdigit()]
        # Always include diff metadata
        choices = [0] + active_hunks
        filename = cur_view().file_name()

        diff, hunk_line_nos = analyze_diff(gen_diff(cur_view()))
        final_line = diff.splitlines()[-1] if diff.splitlines()[-1].startswith('\\') else False

        new_diff = "\n".join("\n".join(hunk) for i, hunk in enumerate(chunk(lines(diff))) if i in choices)
        if final_line and new_diff.splitlines()[-1] != final_line:
            new_diff += ("\n" + final_line)
        new_diff = (new_diff.rstrip(' '))
        if not new_diff.endswith("\n"):
            new_diff += "\n"
        print("new diff: ", new_diff.encode('UTF-8'))
        
        p = subprocess.Popen(['git', 'apply', '--cached', '--recount', '--allow-overlap'], cwd=dirname(cur_view()), stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        print("git staging response: ",p.communicate(input=new_diff.encode('UTF-8')))
        cur_view().run_command('display_hunks')
            
    def run(self):
        sublime.active_window().show_input_panel('Please enter choices: ', '', self.crunch_diff, None, None)

class CommitHunks(sublime_plugin.WindowCommand):
    def commit_patch(self, str):
        p = subprocess.Popen(['git', 'commit', '--file=-'], stderr=subprocess.STDOUT, stdin=subprocess.PIPE, cwd=dirname(cur_view()))
        p.communicate(input=str.encode('utf-8'))
        erase_hunks(cur_view(), 'staged')

    def run(self):
        self.window.show_input_panel('Please enter a commit message: ', '', self.commit_patch, None, None)

class DisplayHunksCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        filename = self.view.file_name()
        if filename:
            paint_hunks(self.view, 'hunks')

            if is_prose(self.view):
                stage_cli =  ['git', 'diff', '--cached', '--unified=1', filename]
            else:
                stage_cli =  ['git', 'diff', '--cached', filename]
            stage_diff = subprocess.check_output(stage_cli, cwd=dirname(self.view), stderr=subprocess.PIPE)
            if stage_diff:
                stage_diff = stage_diff.decode('UTF-8')
                _, stage_lines = analyze_diff(stage_diff)
                print("currently staged for commit: ", stage_lines)
                paint_hunks(self.view, 'staged', hunk_line_nos=stage_lines)
            else:
                erase_hunks(self.view, 'staged')

class ViewHunksCommand(sublime_plugin.WindowCommand):
    """
    When a line with a hunk icon is selected and this command is run, it will open a window
    With that hunk displayed.
    """
    def run(self):
        # active_hunks falls out some times. If I feel lazy I can just run display_hunks right here to get it back
        for r in cur_view().sel():
            pass #I should be able to expand each selection to cover its whole line.

        print("active hunks: ",active_hunks)
        for hunk in active_hunks:
            r = cur_view().get_regions(hunk)

        hunks_to_view = (hunk for hunk, region in active_hunks if cur_view().sel().contains(region))
        print("hunks to view: ", hunks_to_view)
        choices = (int("".join(char for char in name if char.isdigit())) + 1 for name in hunks_to_view)
        print("choices: ",choices)
        diff = gen_diff(cur_view())
        new_diff = "\n".join("\n".join(hunk) for i, hunk in enumerate(chunk(lines(diff))) if i in choices)
        ndw = self.window.new_file()
        ndw.run_command('new_diff', {'nd': new_diff})
        print(new_diff)

class NewDiffCommand(sublime_plugin.TextCommand):
    def run(self, edit, nd=None):
        self.view.set_syntax_file('Packages/Diff/Diff.tmLanguage')
        self.view.insert(edit, 0, nd)

class HunkListener(sublime_plugin.EventListener):
    def on_post_save(self, view):
        view.run_command("display_hunks")

    def on_activated(self, view):
        view.run_command("display_hunks")
