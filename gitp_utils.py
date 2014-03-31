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