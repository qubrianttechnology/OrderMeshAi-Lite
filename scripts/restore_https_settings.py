from pathlib import Path
import json,re
from dotenv import dotenv_values
state_path=Path('.local/https-session.json')
if state_path.exists():
    state=json.loads(state_path.read_text(encoding='utf-8-sig'))
    p=Path('services/api/.env')
    values=dotenv_values(p)
    text=p.read_text(encoding='utf-8-sig')
    expected={'APP_ORIGIN':state['origin'],'WHATSAPP_PUBLIC_CALLBACK_URL':state['origin']+'/webhooks/whatsapp','ALLOW_REGISTRATION':'false','GOOGLE_OAUTH_REDIRECT_URI':state['origin']+'/api/auth/google/callback'}
    for key,old in state['original'].items():
        if values.get(key)!=expected.get(key):
            print('Preserved subsequently edited setting:',key)
            continue
        pattern=r'(?m)^'+re.escape(key)+r'=.*(?:\n|$)'
        replacement='' if old is None else key+'='+old+'\n'
        text=re.sub(pattern,lambda _:replacement,text)
    p.write_text(text,encoding='utf-8')
    print('Restored pre-tunnel app settings without printing credentials.')
