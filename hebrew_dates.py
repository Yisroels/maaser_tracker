# hebrew_dates.py  ← FINAL, CORRECT VERSION (works with convertdate)
from datetime import date, timedelta
from convertdate import hebrew

def get_current_hebrew_year():
    """Returns current Hebrew year (e.g. 5785 for תשפ״ה)"""
    today = date.today()
    hy = hebrew.from_gregorian(today.year, today.month, today.day)[0]
    # Hebrew year starts on 1 Tishrei (month 7)
    if hebrew.from_gregorian(today.year, today.month, today.day)[1] < 7:
        hy -= 1
    return hy

def get_hebrew_year_start_end(hebrew_year):
    """Returns (start_date, end_date) as YYYY-MM-DD strings"""
    # 1 Tishrei of the given Hebrew year
    gy, gm, gd = hebrew.to_gregorian(hebrew_year, 7, 1)  # month 7 = Tishrei
    start_date = f"{gy:04d}-{gm:02d}-{gd:02d}"
    
    # 1 Tishrei of next Hebrew year = end of this year
    gy_next, gm_next, gd_next = hebrew.to_gregorian(hebrew_year + 1, 7, 1)
    end_date = (date(gy_next, gm_next, gd_next) - timedelta(days=1)).strftime('%Y-%m-%d')
    
    return start_date, end_date