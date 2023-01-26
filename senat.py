# %%
import pandas as pd
import tweepy
import requests
from bs4 import BeautifulSoup
import re
from pathlib import Path
import json
import os

# %% [markdown]
# ## La liste des rapports déjà présents

# %%
old_reports_df = pd.read_csv('./rapports-senat.csv', sep=';')
old_reports_df

# %% [markdown]
# ## Quels sont les nouvaux rapports d'information publiés par le Sénat ? 
# 
# Pour le savoir, on a besoin de récupérer la liste sur `http://www.senat.fr/rapports/rapports-information.html`.  
# On va utiliser `bs4` pour parser le HTML.
# 
# - On cherche tous les liens `/notice-rapport/*`

# %%
r = requests.get('http://www.senat.fr/rapports/rapports-information.html')

# %%
soup = BeautifulSoup(r.text, 'html.parser')

# %%
new_reports_urls = []
for a in soup.find(id='encours').parent.find_all(lambda tag: tag.name == 'a' and tag.get('href').startswith('/notice-rapport')):
    [id] = re.findall('notice-rapport\/\d+\/(.+)-notice\.html', a.get('href'))
    if id not in old_reports_df['full_id'].values:
        new_reports_urls.append(a.get('href'))
        

# %%
new_reports_df = pd.DataFrame()
for href in new_reports_urls:
    # id
    [full_id] = re.findall('notice-rapport\/\d+\/(.+)-notice\.html', href)
    # retrieve and parse page
    r = requests.get(f'http://www.senat.fr{href}')
    soup = BeautifulSoup(r.text, 'html.parser')
    # we need:
    # - title
    title = soup.find('h1').text
    # - desc 
    desc = soup.find('h2', {'class': 'subtitle-01'}).text.strip().split('\n')[0]
    # - pdf url
    try:
        pdf_url = soup.find(lambda tag: tag.name == 'a' and tag.get_text() == 'Le rapport au format pdf').get('href')
        pdf_url = f'http://www.senat.fr{pdf_url}'
    except Exception as e:
        print(e)
        pdf_url = ''

    new_reports_df = pd.concat([new_reports_df, pd.Series({
        'full_id': full_id,
        'title': title,
        'desc': desc,
        'pdf_url': pdf_url
    }).to_frame().T])

# %%
new_reports_df

# %% [markdown]
# ## On sauvegarde les nouveaux rapport

# %%
(pd
    .concat([old_reports_df, new_reports_df], ignore_index=True)
    .drop_duplicates(subset=['full_id'])
    .to_csv('./rapports-senat.csv', sep=';', index=False)
)

# %% [markdown]
# ## On les récupère 

# %%
"""
Path('../data/senat/').mkdir(parents=True, exist_ok=True)
for index, row in new_reports_df.iterrows():
    if row['pdf_url']:
        r = requests.get(row['pdf_url'])
        Path(f'../data/senat/{row["full_id"]}.pdf').write_bytes(r.content)
"""

# %% [markdown]
# ## On les tweete

# %%
try:
    credentials = json.load(open('./twitter-credentials.json'))
except:
    # gh actions secrets
    credentials = {key: os.environ[key] for key in ["TWITTER_API_KEY", "TWITTER_API_SECRET", "TWITTER_ACCESS_KEY", "TWITTER_ACCESS_SECRET"]}


# %%
auth = tweepy.OAuthHandler(credentials['TWITTER_API_KEY'], credentials['TWITTER_API_SECRET'])
auth.set_access_token(credentials['TWITTER_ACCESS_KEY'], credentials['TWITTER_ACCESS_SECRET'])
api = tweepy.API(auth)

try:
    api.verify_credentials()
    print("Authentication OK")
except Exception as e:
    print(e)
    print("Error during authentication")

# %%
for index, row in new_reports_df.iterrows():
    tweet = f'ℹ️ • Nouveau rapport d\'information {row["pdf_url"]} {row["title"]}'
    # pour le momnet, on ne tweet que les rapports d'information et d'enquête
    if len(tweet) > 280:
        tweet = tweet[0:277] + '...'    
    print(tweet)
    try:
        api.update_status(tweet)
    except Exception as e:
        print(e)
        print("Error during tweet")


