"""
ทดสอบ _handle_ticket_lookup โดยตรงจาก command line
Usage:
    python test_ticket_lookup.py 540789894
    python test_ticket_lookup.py 540789894 --raw   (แสดง Markdown โดยไม่ strip)
"""
import sys
import asyncio
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Windows terminal อาจใช้ cp874 ซึ่ง encode emoji ไม่ได้ → force UTF-8
if sys.stdout.encoding != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


class FakeMessage:
    def __init__(self):
        self.text = ""

    async def reply_text(self, text, parse_mode=None, reply_markup=None, **kwargs):
        # strip backtick code spans และ bold markers ให้อ่านง่ายขึ้นใน terminal
        import re
        clean = text
        clean = re.sub(r'\*([^*]+)\*', r'\1', clean)   # *bold* → bold
        clean = re.sub(r'`([^`]+)`', r'[\1]', clean)   # `code` → [code]
        clean = re.sub(r'_([^_]+)_', r'\1', clean)     # _italic_ → italic
        print("=" * 60)
        print(clean)
        print("=" * 60)


class FakeUpdate:
    def __init__(self):
        self.message = FakeMessage()


async def main():
    if len(sys.argv) < 2:
        print("Usage: python test_ticket_lookup.py <ticket>")
        print("Example: python test_ticket_lookup.py 540789894")
        sys.exit(1)

    ticket = int(sys.argv[1])
    print(f"Looking up ticket #{ticket} ...")

    from handlers.text_handler import _handle_ticket_lookup

    update = FakeUpdate()
    await _handle_ticket_lookup(update, ticket)


if __name__ == "__main__":
    asyncio.run(main())
