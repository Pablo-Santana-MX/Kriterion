"""Ingestion must be strict: no silent row-dropping."""

import hashlib

import pytest

from kriterion.core.errors import IngestionError
from kriterion.services.ingestion import parse_linearity_csv


def test_basic_with_header():
    raw = b"conc,area\n10,100\n20,200\n"
    out = parse_linearity_csv(raw)
    assert out.concentrations == [10.0, 20.0]
    assert out.areas == [100.0, 200.0]
    assert out.header == ("conc", "area")
    assert out.delimiter == ","
    assert out.source_sha256 == hashlib.sha256(raw).hexdigest()


def test_no_header_semicolon_decimal_comma():
    out = parse_linearity_csv(b"10,5;100,25\n20,5;200,75\n")
    assert out.concentrations == [10.5, 20.5]
    assert out.areas == [100.25, 200.75]
    assert out.header is None


def test_tab_delimited_and_bom_and_crlf():
    out = parse_linearity_csv("﻿C\tA\r\n1\t2\r\n3\t4\r\n".encode("utf-8"))
    assert out.concentrations == [1.0, 3.0]
    assert out.encoding == "utf-8-sig"


def test_cp1252_fallback_warns():
    out = parse_linearity_csv("Concentración;Área\n1;2\n".encode("cp1252"))
    assert out.encoding == "cp1252"
    assert any("Windows-1252" in w for w in out.warnings)


def test_extra_columns_warn():
    out = parse_linearity_csv(b"a,b,c\n1,2,x\n3,4,y\n")
    assert out.rows_read == 2
    assert any("ignored" in w for w in out.warnings)


def test_bad_row_aborts_with_line_number():
    with pytest.raises(IngestionError) as ei:
        parse_linearity_csv(b"c,a\n1,2\n3,oops\n5,6\n")
    assert any("Line 3" in d for d in ei.value.details)


@pytest.mark.parametrize("bad", [b"1,nan", b"1,inf", b"1,1_000", b"1,0x10"])
def test_non_numeric_tokens_rejected(bad):
    with pytest.raises(IngestionError):
        parse_linearity_csv(b"c,a\n" + bad + b"\n")


def test_thousands_separator_rejected_not_guessed():
    with pytest.raises(IngestionError):
        parse_linearity_csv(b"c;a\n1;1.234,5\n")


def test_half_header_row_rejected():
    with pytest.raises(IngestionError):
        parse_linearity_csv(b"10,area\n20,200\n")


@pytest.mark.parametrize("raw", [b"", b"   \n\n", b"\x00\x01\x02,3", b"onlyonecolumn\n1\n2\n"])
def test_empty_binary_or_single_column(raw):
    with pytest.raises(IngestionError):
        parse_linearity_csv(raw)


def test_header_only_has_no_data():
    with pytest.raises(IngestionError):
        parse_linearity_csv(b"conc,area\n")
