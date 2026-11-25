import os

from config import autoclean


async def auto_clean(popped):
    if not popped or not isinstance(popped, dict):
        return
    # Delete playing card message when track ends or is skipped
    try:
        m = popped.get("mystic")
        if m:
            try:
                await m.delete()
            except Exception:
                pass
            popped["mystic"] = None
    except Exception:
        pass

    try:
        rem = popped.get("file")
        if rem and rem in autoclean:
            autoclean.remove(rem)
            count = autoclean.count(rem)
            if count == 0:
                if "vid_" not in rem and "live_" not in rem and "index_" not in rem:
                    try:
                        os.remove(rem)
                    except Exception:
                        pass
    except Exception:
        pass
