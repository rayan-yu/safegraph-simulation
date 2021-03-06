import pandas as pd
import os
import json
import shutil
import gzip
import numpy as np
from distfit import distfit

MINIMUM_RAW_VISITOR_COUNT = 30

WEEK = input('Week (must be a Monday, example: 2020-05-25): ')
STATE_ABBR = input('State abbreviation (example: VA): ')
LOCALITY = input('Locality (example: Fairfax): ')  # can be a county, borough, or parish; independent cities (e.g. Baltimore City) are not currently compatible

if STATE_ABBR == 'AK':
    LOCALITY_TYPE = 'borough'
elif STATE_ABBR == 'LA':
    LOCALITY_TYPE = 'parish'
else:
    LOCALITY_TYPE = 'county'

locality_name = (LOCALITY + ' ' + LOCALITY_TYPE).title()  # e.g. "Fairfax County"

buckets = ['1-5', '6-20', '21-60', '61-240', '241-960']
def get_dwell_distribution(dwell_dictionary):
    nums = list(dwell_dictionary.values())
    print(nums)

    filled_arr = np.empty([1, 1])
    for index, bucket in enumerate(buckets):
        lower, upper = map(int, bucket.split('-'))
        filled_arr = np.concatenate((filled_arr, np.random.uniform(low=lower, high=upper, size=(int(nums[index]), 1))))

    filled_arr = filled_arr[~np.isnan(filled_arr)]

    dist = distfit()
    dist.fit_transform(filled_arr)
    dist_name = dist.model['name']
    
    if len(dist.model['arg']) < 1:
        return (dist_name, dist.model['loc'], dist.model['scale'])
    elif len(dist.model['arg']) == 2:
        return (dist_name, float((dist.model['arg'])[0]), float((dist.model['arg'])[1]), dist.model['loc'], dist.model['scale'])
    else:
        return (dist_name, float((dist.model['arg'])[0]), dist.model['loc'], dist.model['scale'])


# read in FIPS code prefix data
prefix_data = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'safegraph-data', 'safegraph_open_census_data', 'metadata', 'cbg_fips_codes.csv'), error_bad_lines=False)
prefix_row = prefix_data.loc[(prefix_data['county'] == locality_name) & (prefix_data['state'] == STATE_ABBR.upper())]
locality_prefix = str(prefix_row['state_fips'].item()).zfill(2) + str(prefix_row['county_fips'].item()).zfill(3)

core_places_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'safegraph-data', 'safegraph_core_places', 'core_poi.csv')
if not os.path.exists(core_places_path):
    print('Gathering core places information...')
    dfs = []
    for i in range(1, 6):
        dfs.append(pd.read_csv(gzip.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'safegraph-data', 'safegraph_core_places', 'core_poi-part{}.csv.gz'.format(i)), 'rb')))
    core_places = pd.concat(dfs, axis=0, ignore_index=True)
    core_places.to_csv(core_places_path)
else:
    print('Reading core places CSV...')
    core_places = pd.read_csv(core_places_path)
print('Reading POI data...')
data = pd.read_csv(gzip.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'safegraph-data', 'safegraph_weekly_patterns_v2', 'main-file', '{}-weekly-patterns.csv.gz'.format(WEEK)), 'rb'), error_bad_lines=False)
print('Processing POI data...')
county_data = data[(data.raw_visitor_counts >= MINIMUM_RAW_VISITOR_COUNT) & (data.poi_cbg.astype(str).str.startswith(locality_prefix))]
print('Processing core places data and running distributions...')
new_columns = ['top_category', 'sub_category', 'category_tags', 'naics_code', 'brands', 'safegraph_brand_ids', 'parent_safegraph_place_id', 'open_hours', 'postal_code', 'latitude', 'longitude']
county_data['dwell_distribution'] = '()'
for idx, row in county_data.iterrows():
    core_places_row = core_places.loc[core_places['safegraph_place_id'] == row['safegraph_place_id']]
    if len(core_places_row) == 1:
        core_places_row = core_places_row.iloc[0]
        for col in new_columns:
            county_data.loc[idx, col] = core_places_row[col]
    county_data.loc[idx,'dwell_distribution'] = str(get_dwell_distribution(json.loads(row.bucketed_dwell_times)))
print('Writing data...')
print(county_data)
county_data.to_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'parsed-weekly-patterns', '{}-{}-{}-{}.csv'.format(LOCALITY.replace(' ', '-').lower(), LOCALITY_TYPE, STATE_ABBR.lower(), WEEK)))
print('Complete!')
