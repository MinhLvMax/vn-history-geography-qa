class ToolDescriptionPrompt(str):
    def __new__(
            cls,
            name: str,
            description: str,
            arguments: str,
    ):
        text = f"""\
Tool: {name}
Description: {description}
Arguments:
{arguments}
"""
        return super().__new__(cls, text)
