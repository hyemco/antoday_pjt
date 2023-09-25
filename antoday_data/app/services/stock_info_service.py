import FinanceDataReader as fdr
import OpenDartReader
import json
import os
from app.models.database import SessionLocal
from app.models.models import Stock
import datetime
from dateutil.relativedelta import relativedelta
from app.schemas.stocks import StocksDTO
import pandas as pd


# overview
# 현재 종목의 종목정보를 반환하는 함수
def get_stock_info(stock_code):
    dart = get_dart_api()
    value = get_financ_state(stock_code, dart)
    info = get_financ_info(stock_code, dart)

    response_data = {"value": value, "info": info}

    return response_data


# dart api key를 이용해서 api호출
def get_dart_api():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    SECRET_FILE = os.path.join(BASE_DIR, "secrets.json")
    secrets = json.loads(open(SECRET_FILE).read())
    dart = secrets["Dart"]
    return OpenDartReader(dart["api_key"])


# 종목정보
def get_financ_info(stock_code, dart):
    cur_year = datetime.datetime.now().year

    df = fdr.DataReader(stock_code, datetime.datetime.now().strftime("%Y-%m-%d"))
    juga = int(df.head()["Close"].values[0])

    cnt = get_stock_num(stock_code)

    df = dart.finstate(stock_code, cur_year - 1, reprt_code="11011")
    danggi = int(
        df.loc[(df["account_nm"] == "당기순이익") & (df["fs_div"] == "CFS")]["thstrm_amount"]
        .values[0]
        .replace(",", "")
    )
    jabon = int(
        df.loc[(df["account_nm"] == "자본총계") & (df["fs_div"] == "CFS")]["thstrm_amount"]
        .values[0]
        .replace(",", "")
    )
    buchea = int(
        df.loc[(df["account_nm"] == "부채총계") & (df["fs_div"] == "CFS")]["thstrm_amount"]
        .values[0]
        .replace(",", "")
    )

    EPS = danggi / cnt
    PER = juga / EPS
    BPS = (jabon) / cnt
    PBR = juga / BPS
    ROE = danggi / (jabon + buchea) * 100
    ROA = danggi / jabon * 100

    info = {
        "EPS": round(EPS),
        "BPS": round(BPS),
        "PBR": round(PBR, 1),
        "PER": round(PER, 1),
        "ROE": round(ROE, 1),
        "ROA": round(ROA, 1),
    }

    return info


# stock code로 종목수 조회
def get_stock_num(stock_code):
    num = 1
    print("종목수 조회")
    with SessionLocal() as db:
        stocks = db.query(Stock).filter(Stock.stock_code == stock_code).all()
        print(stocks)
        num = stocks[0].stocks

    return num


# 3년치 정보
def get_financ_state(stock_code, dart):
    # 현재년도
    cur_year = datetime.datetime.now().year

    takes = []
    profits = []

    # 3년+현재년도의 데이터에 접근
    for year in range(cur_year - 3, cur_year + 1):
        df = dart.finstate(stock_code, year, reprt_code="11011")
        if df.empty:
            continue

        take = int(
            df.loc[(df["account_nm"] == "매출액") & (df["fs_div"] == "CFS")][
                "thstrm_amount"
            ]
            .values[0]
            .replace(",", "")
        )
        profit = int(
            df.loc[(df["account_nm"] == "영업이익") & (df["fs_div"] == "CFS")][
                "thstrm_amount"
            ]
            .values[0]
            .replace(",", "")
        )

        cur_t = {
            "year": year,
            "take": take,
            "take_kr": get_kor_amount_string_no_change(take),
        }
        cur_p = {
            "year": year,
            "prpfit": profit,
            "profit_kr": get_kor_amount_string_no_change(profit),
        }

        takes.append(cur_t)
        profits.append(cur_p)

    return {"takes": takes, "profits": profits}


# stock
# 주가 차트 데이터 반환하는 함수
def get_stock_price(stock_code, date_option):
    start_date = get_start_date(date_option)

    df = fdr.DataReader(stock_code, start_date)

    # print(df.index.tolist())

    response_data = StocksDTO(
        base_date=start_date,
        # arr=dataframes
        close=df["Close"].tolist(),
        date=df.index.tolist(),
    )

    return response_data


# 현재로부터 date option(3개월, 1년...)전의 날짜를 계산하는 함수
def get_start_date(date_option):
    cur_date = datetime.datetime.now()

    date_option = date_option.split(" ")
    num = int(date_option[0])
    option = date_option[1]

    if option == "개월":
        cur_date = cur_date - relativedelta(months=num)
    elif option == "년":
        cur_date = cur_date - relativedelta(years=num)

    return cur_date.strftime("%Y-%m-01")


# 잔돈은 자르고 숫자를 자릿수 한글단위와 함께 리턴한다
def get_kor_amount_string_no_change(num_amount, ndigits_keep=3):
    if num_amount < 0:
        num_amount *= -1
        return "-" + get_kor_amount_string(
            num_amount, -(len(str(num_amount)) - ndigits_keep)
        )
    return get_kor_amount_string(num_amount, -(len(str(num_amount)) - ndigits_keep))


# 숫자(str)를 한글(ex:3조)로 변환하는 함수
def get_kor_amount_string(num_amount, ndigits_round=0, str_suffix="원"):
    maj_units = ["만", "억", "조", "경", "해", "자", "양", "구", "간", "정", "재", "극"]  # 10000 단위
    units = [" "]  # 시작은 일의자리로 공백으로하고 이후 십, 백, 천, 만...
    for mm in maj_units:
        units.extend(["십", "백", "천"])  # 중간 십,백,천 단위
        units.append(mm)

    list_amount = list(str(round(num_amount, ndigits_round)))  # 라운딩한 숫자를 리스트로 바꾼다
    list_amount.reverse()  # 일, 십 순서로 읽기 위해 순서를 뒤집는다

    str_result = ""  # 결과
    num_len_list_amount = len(list_amount)

    for i in range(num_len_list_amount):
        str_num = list_amount[i]
        # 만, 억, 조 단위에 천, 백, 십, 일이 모두 0000 일때는 생략
        if (
            num_len_list_amount >= 9
            and i >= 4
            and i % 4 == 0
            and "".join(list_amount[i : i + 4]) == "0000"
        ):
            continue
        if str_num == "0":  # 0일 때
            if i % 4 == 0:  # 4번째자리일 때(만, 억, 조...)
                str_result = units[i] + str_result  # 단위만 붙인다
        elif str_num == "1":  # 1일 때
            if i % 4 == 0:  # 4번째자리일 때(만, 억, 조...)
                str_result = str_num + units[i] + str_result  # 숫자와 단위를 붙인다
            else:  # 나머지자리일 때
                str_result = units[i] + str_result  # 단위만 붙인다
        else:  # 2~9일 때
            str_result = str_num + units[i] + str_result  # 숫자와 단위를 붙인다
    str_result = str_result.strip()  # 문자열 앞뒤 공백을 제거한다
    if len(str_result) == 0:
        return None
    if not str_result[0].isnumeric():  # 앞이 숫자가 아닌 문자인 경우
        str_result = "1" + str_result  # 1을 붙인다

    return str_result + str_suffix  # 접미사를 붙인다
