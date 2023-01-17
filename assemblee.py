# %%
import requests
from datetime import datetime
import pandas as pd
import json
import tweepy
import os
from pathlib import Path

# %% [markdown]
# ## On récupère la date du jour

# %%
today = datetime.now()
yesterday = today - pd.Timedelta(days=1)

# %% [markdown]
# ## Quels sont les fichiers publiés en open data aujourd'hui ?

# %%
def retrieve_files_date(date):
    formated_date = date.strftime('%Y-%m-%d')
    try:
        return(pd
            .read_csv(
                f'https://www.assemblee-nationale.fr/dyn/opendata/list-publication/publication_{formated_date}.csv', 
                sep=';', 
                names=['date', 'url']
            )
        )
    except:
        return(pd.DataFrame(columns=['date', 'url']))

files = pd.concat([retrieve_files_date(date) for date in [yesterday, today]], ignore_index=True)

# %% [markdown]
# ## On isole tous les rapports d'information
# 
# - L'id du rapport permet d'accéder au fichier de description json 
# - Si l'id est différent du full_id, cela veut dire que c'est un rapport en plusieurs parties. Il faudra trouver la correspondance dans le fichier de description json

# %%
ris = (files
    # les pdf d'un rapport d'information
    .loc[files['url'].str.contains(r'RIN.+\.pdf$')]    
    .assign(
        full_id = lambda x: x['url'].str.extract(pat = '(RIN.+)\.pdf')        
    )
)

# https://www.codegrepper.com/code-examples/javascript/regex+match+anything+except+character
ris[['id', 'tome']] =  ris['full_id'].str.extract(pat = '(RIN[^-]+)-?(.*)', expand=True)

ris

# %%
raps = (files
    # les pdf d'un rapport
    .loc[files['url'].str.contains(r'RAPP.+\.pdf$')]    
    .assign(
        full_id = lambda x: x['url'].str.extract(pat = '(RAPP.+)\.pdf'),        
    )
)

# https://www.codegrepper.com/code-examples/javascript/regex+match+anything+except+character
raps[['id', 'tome']] =  raps['full_id'].str.extract(pat = '(RAPP[^-]+)-?(.*)', expand=True)

raps

# %%
all_rapports = (pd
    .concat([ris, raps], ignore_index=True)
    .drop_duplicates(subset=['id', 'full_id'])
)

# %%
descriptions = {}
for id in all_rapports['id'].unique():
    url = f'https://www.assemblee-nationale.fr/dyn/opendata/{id}.json'
    response = requests.get(url)
    if response.status_code == 200:
        descriptions[id] = json.loads(response.text)
    else:  
        print(f'{id} not found')

# %% [markdown]
# Pour le moment, on va juste mettre la description de base dans la df

# %%
def get_desc(id):
    return descriptions[id]['titres']['titrePrincipalCourt'].replace("déposé en application de l'article 145 du règlement, ", "")

def get_depot(id):
    return descriptions[id]['classification']['famille']['depot']['code']

def get_type(id):
    if 'libelle' in descriptions[id]['classification']['sousType']:
        return(f"{descriptions[id]['classification']['type']['libelle']} {descriptions[id]['classification']['sousType']['libelle']}")
    else: 
        return descriptions[id]['classification']['type']['libelle']

all_rapports = (all_rapports
    .loc[lambda x: x['id'].isin(descriptions.keys())]
    .assign(
        description = lambda x: x['id'].apply(get_desc),
        rapport_type = lambda x: x['id'].apply(get_type),
        depot = lambda x: x['id'].apply(get_depot)
    )
    # on ne garde que les rapports autonomes
    .loc[lambda x: x['depot'].isin(['RAPAUT'])]
)

all_rapports

# %% [markdown]
# Quels sont les nouveaux RI ?   

# %%
try:
    old_rapports = pd.read_csv('rapports.csv', sep=';')
except:
    old_rapports = pd.DataFrame({'full_id': []})

new_rapports = all_rapports.loc[~all_rapports['full_id'].isin(old_rapports['full_id'])]    
new_rapports

# %% [markdown]
# ## On sauvegarde les nouveaux rapports

# %%
pd.concat([old_rapports, new_rapports], ignore_index=True).to_csv('rapports.csv', sep=';', index=False)

# %% [markdown]
# ## On télécharge les nouveaux fichiers

# %%
def get_dir(type: str):
    if type.startswith("Rapport d'information"):
        return "ris"
    if type.startswith("Rapport d'enquête"):
        return "res"
    else:
        return "raps"
"""
for index, row in new_rapports.iterrows():
    dir = get_dir(row['rapport_type'])
    file = Path(f'../data/assnat/{dir}/{row["full_id"]}.pdf')
    if not file.exists():
        r = requests.get(row['url'])
        if r.status_code == 200:
            file.parent.mkdir(parents=True, exist_ok=True)    
            file.write_bytes(r.content)
"""

# %% [markdown]
# ## On tweete les nouveaux rapports

# %%
try:
    credentials = json.load(open('../twitter-credentials.json'))
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
for index, row in new_rapports.iterrows():
    icons_dict = {
        "Rapport d'information": "ℹ️",
        "Rapport d'information sur des actes de l'Union européenne": "🇪🇺",
        "Rapport d'information d'une mission d'information constituée au sein d'une commission permanente": "🔖",
        "Rapport d'enquête": "🔍"
    }
    icon = icons_dict[row['rapport_type']] if row['rapport_type'] in icons_dict else '📖'
    tweet = f'{icon} • Nouveau {row["rapport_type"].lower()} {row["url"]} {row["description"]}'
    # pour le momnet, on ne tweet que les rapports d'information et d'enquête
    if len(tweet) > 280:
        tweet = tweet[0:277] + '...'    
    print(tweet)
    # api.update_status(tweet)


