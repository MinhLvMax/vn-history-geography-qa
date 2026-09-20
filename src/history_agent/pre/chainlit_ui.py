import chainlit as cl
from src.history_agent.bootstrap import build_agent_controller

agent_controller = build_agent_controller()
history = [
    {
        "role": "system",
        "content": (
            "Bạn là trợ lý AI chuyên về lịch sử và địa lý Việt Nam. "
            "Hãy trả lời bằng tiếng Việt, rõ ràng và chính xác. "
            "Trả lời kèm trích dẫn thông tin nguồn sách và số trang."
            "Nếu không biết hoặc không có đủ thông tin, hãy nói rõ "
            "thay vì tự bịa thông tin."
        ),
    },
    {
        "role": "user",
        "content": "",
    },
]


@cl.on_chat_start
async def on_start():
    '''Khởi tạo'''
    request = {
        "messages": history[:10]
    }
    '''Khai báo request, chỉ lấy 10 turn gần nhất vào lịch sử'''

    response = agent_controller.invoke(
        request
    )

    await cl.Message(
        content=response.content
    ).send()


@cl.on_message
async def handle_message(message: cl.Message):
    # Chat với agent tra cứu
    history.append({
        'role': 'user',
        'content': message.content,
    })

    request = {
        "messages": history[:10]
    }
    '''Khai báo request, chỉ lấy 10 turn gần nhất vào lịch sử'''

    response = agent_controller.invoke(
        request
    )

    await cl.Message(
        content=response.content
    ).send()

    # Hàm chat với llm mặc định
    # await cl.Message(
    #     content=app.chat_usecase.execute(
    #         messages=[{
    #             'role': 'user',
    #             'content': message.content
    #         }],
    #         model='openai/gpt-oss-20b'),
    # ).send()
