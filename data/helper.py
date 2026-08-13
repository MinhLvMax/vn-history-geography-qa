import os
from pathlib import Path
import json
import unicodedata
import re
import uuid
from google import genai
from data.config import Config


def get_file_paths(folder_path):
    return [
        str(Path(folder_path) / name) for name in os.listdir(folder_path)
        if os.path.isfile(os.path.join(folder_path, name))
    ]


def read_text_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def save_text(content: str, output_path: str):
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)


def read_json_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, output_path: str):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def normalize(text: str) -> str:
    text = text.lower()

    text = unicodedata.normalize("NFD", text)
    text = "".join(
        c
        for c in text
        if unicodedata.category(c) != "Mn"
    )

    text = text.replace("đ", "d").replace("Đ", "D")

    text = re.sub(r"[^a-z0-9]+", " ", text)

    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> list[str]:
    text_normalized = normalize(text)
    return text_normalized.split()


def generate_id():
    return str(uuid.uuid4())


def count_tokens(text: str) -> int:
    client = genai.Client(api_key=Config.GOOGLE_API_KEY)

    response = client.models.count_tokens(
        model="gemini-embedding-001",
        contents=text,
    )
    return response.total_tokens

if __name__ == '__main__':
    print(count_tokens(
        '''
        Trong quá trình tiến về phương Nam, khẳng định chủ quyền về lãnh thổ, các chúa Nguyễn sớm có ý thức khẳng định chù quyền của mình đối với các đảo và quần đảo ở mặt Đông, Uong đó có hai quần đảo lớn là Hoàng Sa và Trường Sa. Trước thế kỷ XVII, hai quần đảo này năm trong vùng biển của vưomg quốc Chămpa. Khi vào ưấn thủ Thuận Hóa, các chúa Nguyễn đã chú ý tới việc khai thác các nguồn lợi và thiết lập quyền kiểm soát ưên hai quần đảo này. Các chúa Nguyễn thưòmg cho thuyền đến đảo để lấy vàng bạc và những hải vật quý. Có một nguồn tư liệu xưa nhất (Thiên Nam Tứ chí Lộ Đồ thư hay còn gọi là Toàn tập An Nam Lộ của Đỗ Bá Công Đạo, người huyện Thanh Chương, tinh Nghệ An, soạn vào năm 1686) chua ở phần chú thích của bản đồ rằng: Giữa hiển có một dải cát dài, gọi là bãi cát vàng (nguyên văn: "Hài trung hữu nhất Trường Sa, danh viết bãi cát vàng"... tức Hoàng Sa), dài hơn 400 dặm, rộng 20 dặm, đứng dựng giữa biển Đại Chiêm đến cửa biển Sa Vinh... Họ Nguyễn mỗi năm vào cuối mùa đông đưa 18 chiếc thuyền đến lấy hàng hóa, được phần nhiều là vàng bạc, tiền tệ, súng đạn'. Đen năm 1776, khi Lê Quý Đôn được chính quyền 1. Đỗ Bá Công Đạo, Toàn tập Thiên Nam Tứ chí Lộ Đồ Thư, dẫn theo Nguyễn Nhã, Quá trinh xấc lập chủ quyền của Việt Nam tại quần đảo Hoàng Sa và Trường Sa, Luận án Tiến sĩ Lịch sử, Thành phố Hồ Chí Minh, 2002. Lê - Trịnh cử giữ chức Hiệp trấn quản lãnh hai xứ Thuận Hóa và Quàng Nam vừa chiếm được cùa chúa Nguyễn, ông đã viết Uong Phù biên tạp lục rằng: Phù Quảng Ngãi ở ngoài biên An Vĩnh, huyện Binh Son có núi gọi là Cù Lao Ré, rộng hơn 30 dặm..., phía ngoài nữa lại có đảo Đại Trường Sa, trước kia có nhiều hài vật và hóa vật của tàu, họ Nguyễn đã cho lập ra đội Hoàng Sa để đi lấy...'. Đội Hoàng Sa này gồm 70 người, lấy người An Vĩnh sung vào, cắt phiên moi năm cứ tháng Hai nhận giấy sai đi, mang lương thực đủ ăn 6 tháng, đi bằng 5 chiếc thuyền câu nhó, ra biển 3 ngày 3 đêm thì đến đào ấy. ơ đấy tha hồ bat chim băt cá mà ăn. Lay được hóa vật của tàu, như là gưcrm, ngựa, hoa bạc, tiền bạc, hòn bạc, đồ dùng khối thiếc, khối chì, súng, ngà voi, sáp ong, đô sứ, đồ chiên, đồi moi, ba ba, hải sâm... rat nhiều. Đen tháng Tám thì về đến Cửa Eo, đến kỉnh thành Phú Xuân đế nộp'. Sách Đại Nam thực lục tiền biên của Quốc sử quán triều Nguyễn cũng ghi những sự kiện về hoạt động của đội Hoàng Sa của các chúa Nguyễn tại quần đảo Hoàng Sa như: "ờ ngoài biển về xã An Vĩnh, huyện Bình Sơn, tỉnh Quảng Ngãi, có hơn 130 bãi cát cách nhau đi một ngày hoặc vài trống canh kéo dài không biết mấy nghìn dặm, tục gọi là "Vạn lý Trường Sa". Trên bãi cát có giếng nước ngọt, sản vật có hải sâm, đồi mồi, ốc hoa, ếch, ba ba... Buổi quốc sơ đặt đội Hoàng Sa 70 người, lấy dân xã An Vĩnh sung vào, hàng năm đến tháng 3 thì thuyền ra độ 3 đêm ngày thì đến bãi, tìm hóa vật, đến tháng 8 thì về nộp các đảo thuộc khu vực Hà Tiên (vịnh Thái Lan ngày nay). Cùng với việc thực thi chủ quyền ờ Hoàng Sa và Trường Sa, các chúa Nguyễn cũng chính là những người đầu tiên khẳng định và triển khai hàng loạt các hoạt động chủ quyền ở các đảo Phú Quốc, Thổ Chu, cùng các đảo chính trên vịnh Thái Lan. Sách Phù biên tạp lục ghi: "Họ Nguyễn lại đặt đội Bắc Hải, không định bao nhiêu suất, hoặc người thôn Tứ Chính ở Bình Thuận, hoặc người xã Cảnh Dương, ai tình nguyện đi thì cấp giấy sai đi, miễn cho tiền sưu cùng các tiền tuần đò, cho đi thuyền câu nhỏ ra các xứ Bắc Hải, cù lao Côn Lôn và các đảo ở Hà Tiên, tìm lượng vật của tàu và các thứ đồi mòi, hải ba, bào ngư, hải sâm, cũng sai Cai đội Hoàng Sa kiêm quản"'.
        '''
    ))
