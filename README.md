# tccs — Tiny Claude Code Switch

在多个 LLM 提供商之间快速切换，一键导出对应的环境变量。

## 安装

```bash
# 克隆仓库
git clone git@gitee.com:zzhkikyou/tccs.git

# 放到 PATH 中（可选），例如：
ln -s "$(pwd)/tccs" ~/.local/bin/tccs
```

依赖：Python 3.6+，无第三方库。

## 快速开始

**1. 初始化 shell 集成**

```bash
./tccs
```

此命令会将 `tccs-switch` 和 `tccs-refresh` 函数写入你的 shell 配置文件（`.bashrc` / `.zshrc`）。

**2. 创建 profile**

Profile 是 `~/.tccs/llm_<name>.json` 文件，内容为扁平的环境变量键值对：

```json
{
  "ANTHROPIC_API_KEY": "sk-ant-xxx",
  "ANTHROPIC_MODEL": "claude-sonnet-4-6"
}
```

**3. 切换并激活**

```bash
tccs-switch anthropic    # 需要先完成第 1 步的初始化
```

或者直接：

```bash
eval "$(./tccs -s anthropic)"
```

## 命令参考

| 命令 | 说明 |
|------|------|
| `./tccs` | 初始化，将 shell 函数注入配置文件 |
| `./tccs -a` | 列出所有 profile |
| `./tccs -l` | 显示当前激活的 profile 及其变量 |
| `./tccs -s NAME` | 切换到指定 profile，输出 `export` 语句 |
| `./tccs -e` | 输出当前已激活 profile 的 `export` 语句 |

## 工作原理

```
~/.tccs/
├── llm.json -> llm_anthropic.json   # 符号链接，指向当前激活的 profile
├── llm_anthropic.json               # profile 文件
├── llm_openai.json
└── llm_gemini.json
```

- `tccs -s <name>` 更新符号链接并输出 `export` 行
- `tccs -e` 读取当前符号链接指向的 profile 并输出 `export` 行
- shell 函数 `tccs-switch` / `tccs-refresh` 封装了 `eval "$(tccs ...)"`，使环境变量在当前会话立即生效

## License

MIT
