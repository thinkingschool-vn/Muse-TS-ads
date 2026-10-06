import pytest

from vi_numbers import normalize_numbers, num_to_vi


@pytest.mark.parametrize("n,words", [
    (0, "không"), (5, "năm"), (10, "mười"), (11, "mười một"), (15, "mười lăm"),
    (21, "hai mươi mốt"), (25, "hai mươi lăm"), (105, "một trăm linh năm"),
    (300, "ba trăm"), (2026, "hai nghìn không trăm hai mươi sáu"),
    (60000, "sáu mươi nghìn"), (1200000, "một triệu hai trăm nghìn"),
    (1600000, "một triệu sáu trăm nghìn"), (1000000000, "một tỷ"),
])
def test_num_to_vi(n, words):
    assert num_to_vi(n) == words


def test_dates_money_percent_phone():
    assert normalize_numbers("Ra mắt 11/10") == "Ra mắt mười một tháng mười"
    assert normalize_numbers("Học phí 1.200.000đ") == "Học phí một triệu hai trăm nghìn đồng"
    assert normalize_numbers("1.200.000 đồng") == "một triệu hai trăm nghìn đồng"
    assert normalize_numbers("giảm 25%") == "giảm hai mươi lăm phần trăm"
    assert normalize_numbers("gọi 0909") == "gọi không chín không chín"
    assert normalize_numbers("ngày 11/10/2026") == "ngày mười một tháng mười năm hai nghìn không trăm hai mươi sáu"
