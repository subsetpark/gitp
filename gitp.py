import subprocess, sublime, sublime_plugin

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
    return bool(sum((view.settings().get('syntax').count(lang) for lang in ('Markdown', 'Plain Text'))))

def diff_cli(view):
    filename = view.file_name()
    if is_prose(view):
        return ['git', 'diff', '--unified=1', filename]
    else:
        return ['git', 'diff', filename]

def load_diff(view):
    """
    Analyze a diff file for unidiff content.
    """
    if view.file_name():
        path = dirname(view)
        diff_lines = subprocess.check_output(diff_cli(view), stderr=subprocess.STDOUT, cwd=path).decode('UTF-8').splitlines()
        hunk_metadata = [line.split()[2] for line in diff_lines if line.startswith('@@')]
        hunk_line_nos = [int(word.split(',')[0].translate({ord(i):None for i in '-+,'})) for word in hunk_metadata]
        return diff_lines, hunk_line_nos
    else:
        return None

class EditDiffCommand(sublime_plugin.WindowCommand):
    def crunch_diff(self, str):
        choices = [0] + [int(char) for char in str if char.isdigit()]
        cur_view = self.window.active_view()
        filename = cur_view.file_name()
        path = dirname(cur_view)

        diff = subprocess.check_output(diff_cli(cur_view), cwd=path, stderr=subprocess.STDOUT).decode('UTF-8')
        
        final_line = False
        if diff.splitlines()[-1].startswith('\\'):
            final_line = diff.splitlines()[-1]
        
        new_diff = "\n".join("\n".join(hunk) for i, hunk in enumerate(chunk(lines(diff))) if i in choices)
        if final_line and new_diff.splitlines()[-1] != final_line:
            new_diff += ("\n" + final_line)
        new_diff = new_diff.encode('utf-8')
        
        p = subprocess.Popen(['git', 'apply', '--cached', '--recount', '--allow-overlap'], cwd=path, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        p.communicate(input=new_diff)

    def run(self):
        self.window.show_input_panel('Please enter choices: ', '', self.crunch_diff, None, None)
        self.window.active_view().run_command('display_hunks')

class CommitHunks(sublime_plugin.WindowCommand):
    def commit_patch(self, str):
        path = dirname(self.window.active_view())
        c_msg = str.encode('utf-8')
        p = subprocess.Popen(['git', 'commit', '--file=-'], stderr=subprocess.STDOUT, stdin=subprocess.PIPE, cwd=path)
        p.communicate(input=c_msg)

    def run(self):
        self.window.show_input_panel('Please enter a commit message: ', '', self.commit_patch, None, None)
        self.window.active_view().run_command('display_hunks')

class DisplayHunksCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        cur_view = sublime.active_window().active_view()
        if cur_view.file_name():
            self.view.erase_regions('hunks')
            _, hunk_line_nos = load_diff(cur_view)
            pts = []
            modifier = 2
            if is_prose(cur_view):
                modifier = 1
            if hunk_line_nos: 
                pts = [sublime.Region(cur_view.text_point(l + modifier, 0)) for l in hunk_line_nos]
                cur_view.add_regions("hunks", pts, "hunks", "bookmark", sublime.DRAW_NO_FILL | sublime.PERSISTENT)

class HunkListener(sublime_plugin.EventListener):
    def on_post_save(self, view):
        view.run_command("display_hunks")

    def on_window_command(self, window, command, args):
        window.active_view().run_command('display_hunks')