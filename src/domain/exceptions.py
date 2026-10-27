"""Domain Exceptions - Định nghĩa các lỗi nghiệp vụ trong hệ thống agent.
"""


class AppError(Exception):
    """Lớp cơ sở cho tất cả lỗi nghiệp vụ trong ứng dụng."""
    pass


class ToolDoesNotExist(AppError):
    """Lỗi xảy ra khi tool yêu cầu không tồn tại trong hệ thống."""
    pass


class MessageTypeDoesNotExist(AppError):
    """Lỗi xảy ra khi định dạng message không được hỗ trợ."""
    pass


class APIKeyDoesNotExist(AppError):
    """Lỗi xảy ra khi thiếu API key để kết nối dịch vụ ngoài."""
    pass


class EntityNotFound(AppError):
    """Lỗi xảy ra khi không tìm thấy thực thể cần thao tác trong kho lưu trữ."""
    pass


class EntityAlreadyExists(AppError):
    """Lỗi xảy ra khi thêm thực thể bị trùng (vd. trùng username)."""
    pass


class InvalidCredentials(AppError):
    """Lỗi xảy ra khi đăng nhập sai username hoặc mật khẩu."""
    pass


class Unauthorized(AppError):
    """Lỗi xảy ra khi phiên đăng nhập không hợp lệ hoặc đã hết hạn."""
    pass


class PermissionDenied(AppError):
    """Lỗi xảy ra khi người dùng thao tác trên tài nguyên không thuộc về mình."""
    pass


class InvalidInput(AppError):
    """Lỗi xảy ra khi dữ liệu đầu vào của use case không hợp lệ."""
    pass
