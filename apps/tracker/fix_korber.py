import asyncio
from supabase_service import get_client
from loguru import logger

def reset_korber():
    client = get_client()
    apps = client.table('applications').select('id', 'status_history').ilike('company_name', '%Körber%').execute()
    if not apps.data:
        return
        
    for korber_app in apps.data:
        app_id = korber_app['id']
        history = korber_app.get('status_history', [])
        
        email_ids = []
        for h in history:
            if 'source_email_id' in h: email_ids.append(h['source_email_id'])
            if 'email_id' in h: email_ids.append(h['email_id'])
            
        print(f'Deleting Korber App ID: {app_id} with {len(email_ids)} emails.')
        client.table('applications').delete().eq('id', app_id).execute()
        
        # Also remove them from raw_emails so the pipeline will refetch them
        for eid in email_ids:
            client.table('raw_emails').delete().eq('email_id', eid).execute()

if __name__ == "__main__":
    reset_korber()
