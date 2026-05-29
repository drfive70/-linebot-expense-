import json
import os
import re
from datetime import datetime, timedelta

DATA_FILE = 'expenses.json'
USERS = ['心怡', '70']
HISTORY_KEEP_DAYS = 90  # 保留 3 個月

EMPTY_DATA = {
    "expenses": [],
    "pending_clear": False,
    "history_log": []
}

def _load():
    """每次都從磁碟讀取最新資料"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # 向下相容：補齊缺少的欄位
        if "history_log" not in data:
            data["history_log"] = []
        if "pending_clear" not in data:
            data["pending_clear"] = False
        return data
    return {
        "expenses": [],
        "pending_clear": False,
        "history_log": []
    }

def _save(data):
    """寫回磁碟"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class ExpenseManager:
    """
    每個 public method 開頭都呼叫 _load()，結尾都呼叫 _save()，
    確保多個 gunicorn worker 之間不會互相覆蓋彼此的資料。
    """

    def parse_expense(self, text):
        """
        解析記帳格式：心怡:麥當勞120
        回傳 (欠款方, 說明, 金額) 或 None
        純解析，不讀寫檔案。
        """
        for user in USERS:
            if text.startswith(user + ':') or text.startswith(user + '：'):
                rest = text[len(user) + 1:].strip()
                match = re.search(r'(\d+(?:\.\d+)?)$', rest)
                if match:
                    amount = float(match.group(1))
                    description = rest[:match.start()].strip()
                    if not description:
                        description = '未填說明'
                    return user, description, amount
        return None

    def add_expense(self, debtor, description, amount):
        """記錄一筆欠款：debtor 欠另一方"""
        data = _load()                          # ← 每次重新讀檔
        creditor = [u for u in USERS if u != debtor][0]
        record = {
            "id": len(data["expenses"]) + 1,
            "debtor": debtor,
            "creditor": creditor,
            "amount": amount,
            "description": description,
            "date": datetime.now().strftime("%m/%d"),
            "cleared": False
        }
        data["expenses"].append(record)
        _save(data)                             # ← 寫回磁碟
        return (
            f"✅ 已記錄\n"
            f"{creditor} 幫 {debtor} 付了 ${amount:.0f}（{description}）"
        )

    def get_balance(self):
        """結算：計算未結清帳目，回傳 (摘要文字, 明細文字)"""
        data = _load()
        active = [e for e in data["expenses"] if not e["cleared"]]
        if not active:
            return "🎉 目前沒有未結清帳目！", None

        net = {u: 0.0 for u in USERS}
        details = {u: [] for u in USERS}

        for e in active:
            net[e["debtor"]] += e["amount"]
            details[e["debtor"]].append(f"{e['description']}{e['amount']:.0f}")

        u0, u1 = USERS[0], USERS[1]
        diff = net[u0] - net[u1]

        if abs(diff) < 0.5:
            summary = "🟰 目前兩人帳目相抵，不需要還款！"
        elif diff > 0:
            summary = f"💸 {u0} 要給 {u1}  ${diff:.0f}"
        else:
            summary = f"💸 {u1} 要給 {u0}  ${abs(diff):.0f}"

        detail_lines = []
        for user in USERS:
            if details[user]:
                items = "+".join(details[user])
                detail_lines.append(f"{user}：{items}")

        detail_text = "\n".join(detail_lines) if detail_lines else ""
        return summary, detail_text

    def get_history(self):
        """消費紀錄：依日期倒序，所有未結清紀錄"""
        data = _load()
        active = [e for e in data["expenses"] if not e["cleared"]]
        if not active:
            return "📋 目前沒有消費紀錄"

        lines = ["📋 消費紀錄", "──────────────────"]
        for e in reversed(active):
            lines.append(f"{e['date']} {e['debtor']}：{e['description']}{e['amount']:.0f}")
        return "\n".join(lines)

    def request_clear(self):
        """發起銷帳確認，回傳 (文字訊息 or None, 是否需要 Flex)"""
        data = _load()
        active = [e for e in data["expenses"] if not e["cleared"]]
        if not active:
            return "目前沒有任何未結清帳目，無需銷帳。", False

        data["pending_clear"] = True
        _save(data)
        return None, True

    def confirm_clear(self):
        """確認銷帳：寫入歷史紀錄後清空帳目"""
        data = _load()
        active = [e for e in data["expenses"] if not e["cleared"]]

        if active:
            net = {u: 0.0 for u in USERS}
            for e in active:
                net[e["debtor"]] += e["amount"]

            u0, u1 = USERS[0], USERS[1]
            diff = net[u0] - net[u1]

            if abs(diff) < 0.5:
                settlement = "兩人相抵，無需還款"
            elif diff > 0:
                settlement = f"{u0}給{u1} ${diff:.0f}"
            else:
                settlement = f"{u1}給{u0} ${abs(diff):.0f}"

            dates = sorted(set(e["date"] for e in active))
            date_range = f"{dates[0]}~{dates[-1]}" if len(dates) > 1 else dates[0]

            log_entry = {
                "cleared_date": datetime.now().strftime("%m/%d"),
                "cleared_date_full": datetime.now().strftime("%Y-%m-%d"),
                "settlement": settlement,
                "date_range": date_range,
                "expense_count": len(active)
            }
            data["history_log"].append(log_entry)

            # 清除 3 個月前的舊紀錄
            cutoff = (datetime.now() - timedelta(days=HISTORY_KEEP_DAYS)).strftime("%Y-%m-%d")
            data["history_log"] = [
                log for log in data["history_log"]
                if log.get("cleared_date_full", "9999-99-99") >= cutoff
            ]

        data["expenses"] = []
        data["pending_clear"] = False
        _save(data)
        return "✅ 銷帳完成！所有帳目已清空。"

    def get_history_log(self):
        """歷史訊息：顯示每次銷帳的摘要，最新在上"""
        data = _load()
        logs = data["history_log"]
        if not logs:
            return "📂 目前沒有歷史銷帳紀錄"

        lines = ["📂 歷史銷帳紀錄", "──────────────────"]
        for log in reversed(logs):
            lines.append(
                f"{log['cleared_date']} {log['settlement']}"
                f"（{log['date_range']} 已結清）"
            )
        lines.append("──────────────────")
        lines.append("※ 紀錄保留 3 個月")
        return "\n".join(lines)

    def cancel_clear(self):
        """取消銷帳"""
        data = _load()
        data["pending_clear"] = False
        _save(data)
        return "↩️ 已取消，帳目保持不變。"

    def is_pending_clear(self):
        data = _load()
        return data.get("pending_clear", False)
