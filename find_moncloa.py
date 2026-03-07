import requests
import json
import concurrent.futures

def check_stop(i):
    stop = str(i).zfill(2) # 01, 02.. OR maybe 1, 2, 3.. 4_1, 4_2
    try:
        url = f'https://www.crtm.es/widgets/api/GetStopsTimes.php?codStop=4_{stop}&type=0&orderBy=2&stopTimesByIti='
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            name = data.get('stopTimes', {}).get('stop', {}).get('name', '')
            if 'MONCLOA' in name.upper() or 'CALLAO' in name.upper():
                lines = [l.get('line', {}).get('shortDescription') for l in data.get('stopTimes', {}).get('linesStatus', {}).get('LineStatus', [])]
                if '3' in lines:
                    return f"Found 4_{stop} -> {name} -> Lineas: {lines}"
    except:
        pass
    
    # Try non-padded version
    try:
        url = f'https://www.crtm.es/widgets/api/GetStopsTimes.php?codStop=4_{i}&type=0&orderBy=2&stopTimesByIti='
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            name = data.get('stopTimes', {}).get('stop', {}).get('name', '')
            if 'MONCLOA' in name.upper() or 'CALLAO' in name.upper():
                lines = [l.get('line', {}).get('shortDescription') for l in data.get('stopTimes', {}).get('linesStatus', {}).get('LineStatus', [])]
                if '3' in lines:
                    return f"Found 4_{i} -> {name} -> Lineas: {lines}"
    except:
        pass
    
    return None

with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
    futures = [executor.submit(check_stop, i) for i in range(1, 400)]
    for f in concurrent.futures.as_completed(futures):
        res = f.result()
        if res:
            print(res)

