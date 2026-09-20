from src.history_agent.bootstrap import build_agent_controller


def main():
    controller = build_agent_controller()

    history = [
        {
            "role": "system",
            "content": 'Bạn là trợ lý AI của Minh, không được gọi quá 3 vòng lặp suy nghĩ, nếu kết quả các công cụ không có câu trả lời thì cứ trả lời là bạn không tìm thấy'
        }
    ]

    while True:
        content = input("User: ")

        if content.lower() in ["exit", "quit"]:
            break

        history.append({
            'role': 'user',
            'content': content
        })

        request = {
            "messages": history[:10]
        }
        '''Khai báo request, chỉ lấy 10 turn gần nhất vào lịch sử'''

        response = controller.invoke(
            request
        )

        history.append({
            'role': response.role,
            'content': response.content
        })

        print("Agent:", response.content)


if __name__ == "__main__":
    main()
