从其他工具启动 VS Code 选项卡
该扩展在 vscode://anthropic.claude-code/open 处注册了一个 URI 处理程序。使用它从您自己的工具中打开新的 Claude Code 选项卡：shell 别名、浏览器书签或任何可以打开 URL 的脚本。如果 VS Code 尚未运行，打开 URL 会首先启动它。如果 VS Code 已在运行，URL 会在当前获得焦点的窗口中打开。
使用您的操作系统的 URL 打开器调用处理程序。
macOS
Linux
Windows
open "vscode://anthropic.claude-code/open"
处理程序接受两个可选的查询参数：
参数	描述
prompt	要在提示框中预填充的文本。必须进行 URL 编码。提示框被预填充但不会自动提交。
session	要恢复的会话 ID，而不是启动新对话。会话必须属于 VS Code 中当前打开的工作区。如果找不到会话，将启动新的对话。如果会话已在选项卡中打开，该选项卡将获得焦点。要以编程方式捕获会话 ID，请参阅 继续对话。
例如，要打开一个预填充”review my changes”的选项卡：
vscode://anthropic.claude-code/open?prompt=review%20my%20changes