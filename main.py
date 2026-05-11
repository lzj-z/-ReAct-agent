from langchain_core.messages import AIMessage, ToolMessage
from agent.agent_react import ReactAgent


def main():
    agent = ReactAgent()
    history = []
    print("=" * 50)
    print("  智扫通机器人智能客服  (输入 exit 退出)")
    print("=" * 50)

    while True:
        try:
            user_input = input("\n你：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n对话结束。")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "退出"):
            print("感谢使用，再见！")
            break

        history.append({"role": "user", "content": user_input})
        print("\n客服：", end="", flush=True)

        final_text = ""
        for chunk in agent.agent.stream({"messages": history}):
            for _, node_output in chunk.items():
                if not isinstance(node_output, dict):
                    continue
                msgs = node_output.get("messages", [])
                for msg in msgs:
                    if isinstance(msg, ToolMessage):
                        # 工具返回结果：换行展示，便于观察调用过程
                        print(f"\n  [工具返回·{msg.name}] {msg.content[:200]}", flush=True)
                    elif isinstance(msg, AIMessage):
                        if msg.tool_calls:
                            for tc in msg.tool_calls:
                                print(f"\n  [调用工具] {tc['name']}  入参：{tc['args']}", flush=True)
                            print("\n客服：", end="", flush=True)
                        if msg.content:
                            # 最终流式文字回答
                            print(msg.content, end="", flush=True)
                            final_text = msg.content

        print()  # 换行
        if final_text:
            history.append({"role": "assistant", "content": final_text})


if __name__ == "__main__":
    main()
