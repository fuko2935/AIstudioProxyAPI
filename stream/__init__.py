import asyncio
import multiprocessing

from stream import main

def start(*args, **kwargs):
    """
    Akış proxy sunucusunu başlat, konum bağımsız değişkenleri ve anahtar kelime bağımsız değişkenleri ile uyumlu

    Konum bağımsız değişkenleri modu (referans dosya ile uyumlu):
        start(queue, port, proxy)

    Anahtar kelime bağımsız değişkenleri modu:
        start(queue=queue, port=port, proxy=proxy)
    """
    if args:
        # Konum bağımsız değişkenleri modu (referans dosya ile uyumlu)
        queue = args[0] if len(args) > 0 else None
        port = args[1] if len(args) > 1 else None
        proxy = args[2] if len(args) > 2 else None
    else:
        # Anahtar kelime bağımsız değişkenleri modu
        queue = kwargs.get('queue', None)
        port = kwargs.get('port', None)
        proxy = kwargs.get('proxy', None)

    asyncio.run(main.builtin(queue=queue, port=port, proxy=proxy))