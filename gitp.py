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


def dirname(view):
    filename = view.file_name()    if not filename:
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
    return bool(sum((view.settings().get('syntax').count(lang) for lang in ('Markdown', 'Plain Text'))))

def diff_cli(view):
    filename = view.file_name()
    if is_prose(view):
        return ['git', 'diff', '--unified=1', filename]
    else:
        return ['git', 'diff', filename]

def gen_diff(view):
    if view.file_name():
        path = dirname(view)
        return subprocess.check_output(diff_cli(view), stderr=subprocess.STDOUT, cwd=path).decode('UTF-8')
    else:
        return None

def analyze_diff(diff):
    """
    Analyze a diff file for unidiff content.
    """
    diff_lines = diff.splitlines()
    hunk_metadata = [line.split()[2] for line in diff_lines if line.startswith('@@')]
    hunk_line_nos = [int(word.split(',')[0].translate({ord(i):None for i in '-+,'})) for word in hunk_metadata]
    return diff, hunk_line_nos

def erase_hunks(view, key):
    if key == "hunks":
        for i in range(len(DIGITS)):
            view.erase_regions('gitp_hunks'+str(i))
    else:
        view.erase_regions(key)

def paint_hunks(view, key, hunk_line_nos=None):
    if view.file_name():        erase_hunks(view, key)
        if not hunk_line_nos:
            _, hunk_line_nos = analyze_diff(gen_diff(view))
        pts = []
        modifier = 1 if is_prose(view) else 2
        if hunk_line_nos: 
            pts = [sublime.Region(view.text_point(l + modifier, 0)) for l in hunk_line_nos]
            if key == "hunks":
                for i, pt in enumerate(pts):
                    keyname = 'gitp_hunks'+str(i)
                    digit = DIGITS[i] if i < len(DIGITS) else 'bookmark'
                    view.add_regions(keyname, [pt], keyname, digit, sublime.DRAW_NO_FILL | sublime.PERSISTENT)
            else:
                print("adding regions with key", key)
                view.add_regions(key, pts, key, ICONS[key], sublime.HIDDEN | sublime.PERSISTENT)

class EditDiffCommand(sublime_plugin.WindowCommand):
    def crunch_diff(self, str):
        active_hunks = [int(char) for char in str if char.isdigit()]
        choices = [0] + active_hunks
        filename = cur_view().file_name()
        path = dirname(cur_view())

        diff, hunk_line_nos = analyze_diff(gen_diff(cur_view()))
        final_line = diff.splitlines()[-1] if diff.splitlines()[-1].startswith('\\') else False
        
        new_diff = "\n".join("\n".join(hunk) for i, hunk in enumerate(chunk(lines(diff))) if i in choices)
        if final_line and new_diff.splitlines()[-1] != final_line:
            new_diff += ("\n" + final_line)
        new_diff = (new_diff.rstrip(' ') + "\n") if not new_diff.endswith("\n") else new_diff.rstrip(' ')
        print("new diff: ", new_diff.encode('UTF-8'))
        p = subprocess.Popen(['git', 'apply', '--cached', '--recount', '--allow-overlap'], cwd=path, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        print(p.communicate(input=new_diff.encode('UTF-8')))
        cur_view().run_command('display_hunks')
            
    def run(self):
        sublime.active_window().show_input_panel('Please enter choices: ', '', self.crunch_diff, None, None)

class CommitHunks(sublime_plugin.WindowCommand):
    def commit_patch(self, str):
        path = dirname(cur_view())
        c_msg = str.encode('utf-8')
        p = subprocess.Popen(['git', 'commit', '--file=-'], stderr=subprocess.STDOUT, stdin=subprocess.PIPE, cwd=path)
        p.communicate(input=c_msg)
        erase_hunks(cur_view(), 'staged')

    def run(self):
        self.window.show_input_panel('Please enter a commit message: ', '', self.commit_patch, None, None)
        sublime.set_timeout(lambda: cur_view().run_command('display_hunks'), 2000)

class DisplayHunksCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        filename = cur_view().file_name()
        if filename:
            path = dirname(cur_view())
            paint_hunks(cur_view(), 'hunks')

            if is_prose(cur_view()):
                stage_cli =  ['git', 'diff', '--cached', '--unified=1', filename]
            else:
                stage_cli =  ['git', 'diff', '--cached', filename]            stage_diff = subprocess.check_output(stage_cli, cwd=path, stderr=subprocess.PIPE)
            if stage_diff:
                stage_diff = stage_diff.decode('UTF-8')
                _, stage_lines = analyze_diff(stage_diff)
                print(stage_lines)
                paint_hunks(cur_view, 'staged', hunk_line_nos=stage_lines)

class HunkListener(sublime_plugin.EventListener):
    def on_post_save(self, view):
        view.run_command("display_hunks")

    def on_window_command(self, window, command, args):
        window.active_view().run_command('display_hunks')