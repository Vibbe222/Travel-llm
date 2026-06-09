import gradio as gr

from chat_service import create_session, iter_chat_events

session = create_session()
thread_id = session["thread_id"]
config = session["config"]
print("thread_id:", thread_id)


async def process_message(user_message, chatbot_history, debug_history):
    chatbot_history.append((user_message, None))

    async for event in iter_chat_events(user_message=user_message, config=config):
        kind = event["type"]

        if kind == "chunk":
            content = event["content"]
            if content:
                if chatbot_history and chatbot_history[-1][1] is not None:
                    chatbot_history[-1] = (
                        chatbot_history[-1][0],
                        chatbot_history[-1][1] + content,
                    )
                else:
                    chatbot_history[-1] = (chatbot_history[-1][0], content)
                yield chatbot_history, debug_history

        elif kind == "tool_start":
            debug_history += (
                f"Starting tool: {event['name']} "
                f"with inputs: {event.get('input')}\n"
            )
            yield chatbot_history, debug_history

        elif kind == "tool_end":
            debug_history += (
                f"Done tool: {event['name']}\n"
                f"Tool output: {event.get('output')}\n--\n"
            )
            yield chatbot_history, debug_history


def clear_input():
    return ""


def start_gradio():
    with gr.Blocks() as demo:
        gr.Markdown("# 基于 LangGraph 的旅游规划助手")

        with gr.Row(equal_height=True) as chat_interface:
            chat_interface.elem_classes = ["full-height"]

            with gr.Column(scale=1):
                debug_info = gr.Textbox(
                    label="Debug Info",
                    lines=30,
                    interactive=False,
                    elem_id="debug-info",
                )

            with gr.Column(scale=3):
                chatbot = gr.Chatbot(
                    label="User-AI Chat",
                    show_label=False,
                    elem_id="chatbot",
                )

                user_input = gr.Textbox(
                    label="Your message",
                    placeholder="Type your message here",
                    lines=3,
                    max_lines=5,
                    show_label=False,
                    elem_id="user-input",
                )

                submit_click = gr.Button("Send")

        def submit_action():
            return process_message, [user_input, chatbot, debug_info], [chatbot, debug_info]

        submit_click.click(*submit_action()).then(clear_input, None, user_input)
        user_input.submit(*submit_action()).then(clear_input, None, user_input)

    demo.launch()


if __name__ == "__main__":
    start_gradio()

