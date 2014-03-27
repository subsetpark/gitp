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
    yield chunk

class EditDiffCommand(sublime_plugin.WindowCommand):
    def crunch_diff(self, str):
        choices = [0] + [int(char) for char in str.split() if char.isdigit()]
        filename = self.window.active_view().file_name()
        diff = subprocess.check_output(['git', 'diff', filename]).decode('UTF-8')
        new_diff = "\n".join("\n".join(hunk) for i, hunk in enumerate(chunk(lines(diff))) if i in choices)
        if new_diff[-1] != "\n":
            new_diff += "\n"
        p = subprocess.Popen(['git', 'apply', '--cached', '--recount', '--allow-overlap'], stderr=subprocess.STDOUT, stdin=subprocess.PIPE,  universal_newlines=True)
        p.communicate(input=new_diff)

    def run(self):
        self.window.show_input_panel('Please enter choices: ', '', self.crunch_diff, None, None)
        self.load_diff()
        pass

class DisplayHunksCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.view.erase_regions('mark')
        _, hunk_line_nos = self.load_diff()
        pts = [sublime.Region(self.view.text_point(l, 0)) for l in hunk_line_nos]
        self.view.add_regions("hunks", pts, "hunks", "dot", sublime.HIDDEN | sublime.PERSISTENT)

    def load_diff(self):
        diff_lines =  subprocess.check_output(['git', 'diff', filename],
                    stderr=subprocess.STDOUT).decode('UTF-8').splitlines()
        hunk_metadata = [line.split()[1] for line in diff_lines if line.startswith('@@')]
        hunk_line_nos = [int(word.split(',')[0].translate({ord(i):None for i in '-+,'})) for word in hunk_metadata]
        return diff_lines, hunk_line_nos

class HunkListener(sublime_plugin.EventListener):
    def on_post_save(self, view):
        view.run_command("display_hunks")