`gitp` is a Sublime Text plugin currently in development that provides a frontend to `git add -p`. 

## Patch Mode

git has a very powerful and somewhat obscure command called `add -p`, or patch mode. 

```diff
➜  gitp git:(master) ✗ git add -p
diff --git a/README.md b/README.md
index 7599136..239c049 100644
--- a/README.md
+++ b/README.md
@@ -1,5 +1,9 @@
 `gitp` is a Sublime Text plugin currently in development that provides a frontend to `git add -p`.

+## Patch Mode
+
+git has a very powerful and somewhat obscure command called `add -p`, or patch mode.
+
 It represents changed hunks with number icons in the Sublime Text gutter.

 It supports the following commands:
Stage this hunk [y,n,q,a,d,/,e,?]?
```

This allows you to selectively stage parts of a file for commit, rather than staging the entire file at once. So if you last committed a certain file 6 hours ago, during which time you implemented one bugfix, one new feature, and added some documentation, you don't have to stage those three disparate changes into one commit. Instead you can use `git add -p` to selectively stage only the hunks related to the bugfix, then commit that, do the same for the new feature, et cetera. 

## gitp

`gitp` is a plugin for Sublime Text 3 that attempts to expose `git add -p` as thoroughly as possible, so that you don't have to leave your text editor and use the command line-based interactive perl script to use it, if you don't want to.

### Displaying changed hunks

`gitp` represents changed hunks[^1] with number icons in the Sublime Text gutter. 

### Staging changed hunks

There are two ways to stage an individual hunk for commit in `gitp`: 

- `ctrl-alt-x` : **edit diff**. The user is prompted for the digits of the changed hunks that they'd like to stage for commit.

- `ctrl-alt-s` : **stage these hunks**. If one or more lines with changed hunk indicators on them (ST's multiple cursors are supported) are selected, this command will stage them all.

### Viewing hunks

- `ctrl-alt-v` : **view these hunks**. View the diffs for all currently-selected hunks.

If one or more lines with hunk indicators are selected, this command will display the changes between the currently saved version and the most recent commit.

### Unstaging

- `ctrl-alt-z` : **unstage hunks**. Clears staged hunks.

### Committing hunks

- `ctrl-alt-c` : **commit staged hunks**. The user is prompted for a commit message and all staged hunks are committed.

[^1]: Hunks are discrete areas of changed text in a diff file. They are represented as one or more changed lines, surrounded by a little bit of context, and headed by a metadata line that starts with '@@'.