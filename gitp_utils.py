import subprocess, io

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

def load_diff(filename, syntax):
    if sum((syntax.count(lang) for lang in ('Markdown', 'Plain Text'))):
        diff_cli = ['git', 'diff', '--unified=1', filename]
    else:
        diff_cli = ['git', 'diff', filename]
    diff_lines =  subprocess.check_output(diff_cli, stderr=subprocess.STDOUT).decode('UTF-8').splitlines()
    hunk_metadata = [line.split()[1] for line in diff_lines if line.startswith('@@')]
    hunk_line_nos = [int(word.split(',')[0].translate({ord(i):None for i in '-+,'})) for word in hunk_metadata]
    return diff_lines, hunk_line_nos
# Here is a trivial change
def new_diff(filename):
    diff = subprocess.check_output(['git', 'diff', filename]).decode('UTF-8')
    if diff.splitlines()[-1].startswith('\\'):
        final_line = diff.splitlines()[-1]
    print("diff: ", diff)
    str = input("Choices:")
    choices = [0] + [int(char) for char in str.split() if char.isdigit()]
    new_diff = "\n".join("\n".join(hunk) for i, hunk in enumerate(chunk(lines(diff))) if i in choices)
    if final_line and new_diff.splitlines()[-1] != final_line:
        new_diff += "\n" + final_line
    print("new diff: ", new_diff)
    apply = input("apply? ")
    if apply:
        new_diff = new_diff.encode('utf-8')
        p = subprocess.Popen(['git', 'apply', '--cached', '--recount', '--allow-overlap'], stderr=subprocess.STDOUT, stdin=subprocess.PIPE)
        p.communicate(input=new_diff)
    
if __name__ == "__main__":
    new_diff('poem.md')