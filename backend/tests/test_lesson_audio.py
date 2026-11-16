from app.routers.lesson_audio import parse_unit_label


def test_parse_unit_label_unit_number():
    assert parse_unit_label("01_Unit 1.mp3") == "Unit 1"
    assert parse_unit_label("02_Unit 2.mp3") == "Unit 2"
    assert parse_unit_label("08_Unit 8.mp3") == "Unit 8"


def test_parse_unit_label_word_list():
    assert parse_unit_label("09_Word list.mp3") == "Word list"


def test_parse_unit_label_fallback():
    # 无法解析时回落：去扩展名的原始文件名
    assert parse_unit_label("whatever.mp3") == "whatever"
    assert parse_unit_label("Unit.mp3") == "Unit"
