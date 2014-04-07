`gitp` is a Sublime Text plugin currently in development that provides a frontend to `git add -p`. 

It represents changed hunks with number icons in the Sublime Text gutter.

It supports the following commands:

- `ctrl-alt-x` : **stage hunks**. Enter the numbers of the hunks you wish to stage and they will be staged for commit.
- `ctrl-alt-s` : **stage these hunks**. Stage all currently-selected hunks.
- `ctrl-alt-v` : **view these hunks**. View the diffs for all currently-selected hunks.
- `ctrl-alt-c` : **commit staged hunks**. Enter a commit message to commit all staged hunks.