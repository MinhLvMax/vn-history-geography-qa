class CompleteResult:
    def __init__(self, content=None, total_tokens=None, total_time=None, cached_tokens=None, response_model=None):
        self.content = content
        self.total_tokens = total_tokens
        self.total_time = total_time
        self.cached_tokens = cached_tokens
        self.response_model = response_model