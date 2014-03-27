import subprocess, sublime, sublime_plugin

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

class EditDiffCommand(sublime_plugin.TextCommand):
    def run(self):
        filename = self.view.file_name()
        diff = subprocess.check_output(['git', 'diff', filename]).decode('UTF-8')
        for hunk in chunk(lines(diff)):
            sublime.message_dialog(hunk)

class DisplayHunksCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.view.erase_regions('mark')
        _, hunk_line_nos = self.load_diff()
        pts = [sublime.Region(self.view.text_point(l, 0)) for l in hunk_line_nos]
        self.view.add_regions("hunks", pts, "hunks", "dot", sublime.HIDDEN | sublime.PERSISTENT)

    def load_diff(self):
        diff_lines =  subprocess.check_output(['git', 'diff', filename]).decode('UTF-8').splitlines()
        hunk_metadata = [line.split()[1] for line in diff_lines if line.startswith('@@')]
        hunk_line_nos = [int(word.split(',')[0].translate({ord(i):None for i in '-+,'})) for word in hunk_metadata]
        return diff_lines, hunk_line_nos

class HunkListener(sublime_plugin.EventListener):
    def on_post_save(self, view):
        view.run_command("display_hunks")