import json
import os
from datetime import datetime
from collections import defaultdict

DATA_FILE = 'expenses.json'

class ExpenseManager:
    def __init__(self):
        self.data = self._load()

    def _load(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"expenses": [], "cleared": []}

    def _save(self):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def add_expense(self, payer, amount, description):
        record = {
            "id": len(self.data["expenses"]) + 1,
            "payer": payer,
            "amount": amount,
            "description": description,
            "date": datetime.now().strftime("%m/%d %H:%M"),
            "cleared": False
        }
        self.data["expenses"].append(record)
        self._save()
        return (
            f"✅ 已記錄！\n"
            f"──────────────────\n"
            f"👤 付款人：{payer}\n"
            f"💴 金額：${amount:.0f}\n"
            f"📝 說明：{description}\n"
            f"🕐 時間：{record['date']}\n"
            f"──────────────────\n"
            f"輸入「結算」查看欠款狀況"
        )

    def get_summary(self):
        active = [e for e in self.data["expenses"] if not e["cleared"]]
        if not active:
            return "📒 目前沒有未結清的帳目\n\n輸入「歷史」查看所有紀錄"

        lines = ["📒 未結清帳目", "──────────────────"]
        total_by_person = defaultdict(float)

        for e in active:
            lines.append(f"#{e['id']} {e['date']} {e['payer']} 付了 ${e['amount']:.0f}（{e['description']}）")
            total_by_person[e['payer']] += e['amount']

        lines.append("──────────────────")
        lines.append("📊 各人小計：")
        for person, total in total_by_person.items():
            lines.append(f"  {person}：共付 ${total:.0f}")

        lines.append("\n輸入「結算」查看誰欠誰多少")
        return "\n".join(lines)

    def get_balance(self):
        active = [e for e in self.data["expenses"] if not e["cleared"]]
        if not active:
            return "🎉 目前沒有未結清帳目！"

        # 計算每人總付款
        paid = defaultdict(float)
        people = set()
        for e in active:
            paid[e['payer']] += e['amount']
            people.add(e['payer'])

        total = sum(paid.values())
        share = total / len(people) if people else 0

        lines = ["💰 結算報告", "──────────────────"]
        lines.append(f"總金額：${total:.0f}")
        lines.append(f"人數：{len(people)}人")
        lines.append(f"每人應付：${share:.0f}")
        lines.append("──────────────────")

        debts = []
        for person in people:
            diff = paid[person] - share
            if diff > 0.5:
                lines.append(f"✅ {person} 多付了 ${diff:.0f}")
            elif diff < -0.5:
                lines.append(f"⚠️ {person} 少付了 ${abs(diff):.0f}")
                debts.append((person, abs(diff)))
            else:
                lines.append(f"🟰 {person} 剛好平")

        if debts:
            lines.append("──────────────────")
            lines.append("📌 應還款：")
            for person, amount in debts:
                # 找出多付的人
                creditors = [(p, paid[p] - share) for p in people if paid[p] - share > 0.5]
                for creditor, _ in creditors:
                    lines.append(f"  {person} 需還 {creditor} ${amount:.0f}")

        lines.append("──────────────────")
        lines.append("還款後輸入：還清 [名字]")
        return "\n".join(lines)

    def clear_balance(self, person):
        cleared_count = 0
        for e in self.data["expenses"]:
            if e['payer'] == person and not e['cleared']:
                e['cleared'] = True
                cleared_count += 1
        
        if cleared_count == 0:
            # 嘗試標記該人的債務已還清（記一筆還款紀錄）
            record = {
                "id": len(self.data["expenses"]) + 1,
                "payer": person,
                "amount": 0,
                "description": "【還款記錄】",
                "date": datetime.now().strftime("%m/%d %H:%M"),
                "cleared": True
            }
            self.data["expenses"].append(record)
            self._save()
            return f"✅ 已標記 {person} 的帳目已結清！"

        self._save()
        return (
            f"✅ 已將 {person} 的 {cleared_count} 筆帳目標記為已結清！\n"
            f"輸入「帳目」查看剩餘未結清項目"
        )

    def delete_last(self):
        active = [e for e in self.data["expenses"] if not e["cleared"]]
        if not active:
            return "沒有可刪除的帳目"
        last = active[-1]
        self.data["expenses"].remove(last)
        self._save()
        return (
            f"🗑️ 已刪除最後一筆：\n"
            f"  {last['payer']} 付了 ${last['amount']:.0f}（{last['description']}）"
        )

    def get_history(self):
        all_expenses = self.data["expenses"]
        if not all_expenses:
            return "📋 還沒有任何紀錄"

        lines = ["📋 所有紀錄（含已結清）", "──────────────────"]
        for e in all_expenses[-20:]:  # 最近20筆
            status = "✅" if e["cleared"] else "⏳"
            if e["amount"] > 0:
                lines.append(f"{status} #{e['id']} {e['date']} {e['payer']} ${e['amount']:.0f} {e['description']}")
        
        if len(all_expenses) > 20:
            lines.append(f"（只顯示最近20筆，共{len(all_expenses)}筆）")
        
        return "\n".join(lines)
