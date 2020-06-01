import numpy as np
import pandas as pd
import pickle
import os

import lightgbm as lgb
import statsmodels.api as sm
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors
##############################################################################
##############################################################################
model_path = "/Users/christianhilscher/desktop/dynsim/src/estimation/models/"
estimation_path = "/Users/christianhilscher/desktop/dynsim/src/estimation/"
sim_path = "/Users/christianhilscher/desktop/dynsim/src/sim/"
input_path = "/Users/christianhilscher/Desktop/dynsim/input/"

os.chdir(estimation_path)
from standard import data_birth
from extended import data_general

os.chdir(sim_path)
##############################################################################
mortality = pd.read_csv(input_path + "mortality")
fertility = pd.read_csv(input_path + "fertility")
##############################################################################


def death(dataf):
    dataf = dataf.copy()

    deaths = np.zeros(len(dataf))
    deaths[dataf['age']>dataf['age_max']] = 1
    if np.sum(deaths)>0:
        dataf.drop(deaths, inplace=True)
    else:
        pass
    return dataf, np.sum(deaths)


def dating_market(dataf):
    """
    New couples finding together. Right now 20% of the singles find a new partner.
    """
    dataf = dataf.copy()

    eligible = (dataf['in_couple'] == 0) & (dataf['child'] == 0) & (dataf['n_people'] - dataf['n_children'] == 1)

    female_singles = dataf[eligible & (dataf['female'] == 1)]
    male_singles = dataf[eligible & (dataf['female'] == 0)]

    not_single = dataf[~eligible]

    new_couples = round(0.1 * min(len(female_singles),
                                  len(male_singles)))

    if new_couples>0:
        matching_dict = _matching(female_singles,
                                  male_singles,
                                  new_couples)

        dataf_out = pd.concat((not_single,
                               matching_dict['girls'],
                               matching_dict['guys']), axis=0)

        assert(
            len(matching_dict['girls']) == len(female_singles)
        ), 'Lenght of dataframe is not the same as before'
    else:
        dataf_out = dataf

    return dataf_out, new_couples

def _matching(females, males, number):
    """
    Finding the 5 best fitting matches and then choosing randomly.
    #TODO: think of a better way than this loop
    """
    partners = females.copy()
    lucky_guys = males.sample(number)

    neigh = NearestNeighbors(n_neighbors=5)

    happy_girls = pd.DataFrame()

    # Looping since as soon as one couple matched, that woman is no longer available
    for i in np.arange(len(lucky_guys)):
        neigh.fit(partners[['age',
                            'education',
                            'migback',
                            'east',
                            'n_children']])
        bachelor = lucky_guys.iloc[i,:]
        bachelor = bachelor[['age',
                             'education',
                             'migback',
                             'east',
                             'n_children']].to_numpy().reshape(1,-1)

        partner_choice = neigh.kneighbors(bachelor)

        partner = np.random.choice(np.ravel(partner_choice[1]), 1)
        happy_girls = pd.concat([happy_girls, partners.iloc[partner,:]])
        partners.drop(partners.iloc[partner,:].index, inplace=True)


    happy_girls, lucky_guys = _adjust_values(happy_girls, lucky_guys)

    singles_dict = {'all_female': females,
                'all_male': males,
                'happy_girls': happy_girls,
                'lucky_guys': lucky_guys}

    out_dict = _concat_singles(singles_dict)

    return out_dict

def _concat_singles(dici):
    """
    Concating those who found new partners and those who didn't
    """

    unlucky_guys = dici['all_male'][dici['all_male'].index.isin(dici['lucky_guys'].index) == False]

    unhappy_girls = dici['all_female'][dici['all_female'].index.isin(dici['happy_girls'].index) == False]

    girls = pd.concat((dici['happy_girls'], unhappy_girls), axis = 0)
    guys = pd.concat((dici['lucky_guys'], unlucky_guys), axis = 0)

    assert(
        len(unlucky_guys) + len(dici['lucky_guys']) == len(dici['all_male'])
    ), "Error in concating guys"

    assert(
        len(unhappy_girls) + len(dici['happy_girls']) == len(dici['all_female'])
    ), "Error in concating girls"

    out_dict = {'girls' : girls,
                'guys': guys}
    return out_dict

def _adjust_values(females, males):
    """
    Adjusting the values as the man moves in with the woman
    """
    females = females.copy()
    males = males.copy()

    males.loc[:,'hid'] = females['hid'].tolist()
    males.loc[:,'east'] = females['east'].tolist()
    males.loc[:,'hhweight'] = females['hhweight'].tolist()
    males.loc[:,'in_couple'] = 1
    females.loc[:,'in_couple'] = 1

    return females, males

def separations(dataf):
    """
    Calculates the seperations in each period.
    Only those who are married or in a relationship (in_couple) can separate
    """
    dataf = dataf.copy()

    probability = np.random.uniform(0, 1, len(dataf))
    condition_married = (dataf['married'] == 1) & (probability<0.01)
    condition_incouple = (dataf['in_couple'] == 1) & (dataf['married'] == 0) & (probability<0.02)
    condition_separation = (condition_married | condition_incouple)

    males = (condition_separation) & (dataf['female'] == 0)
    dataf.loc[condition_separation, ['married', 'in_couple']] = [[0, 0]]

    # Men move out; resetting HID
    dataf.loc[males, 'orighid'] = dataf.loc[males, 'hid'].copy()
    dataf.loc[males, 'hid'] += np.arange(1, np.sum(males)+1)

    separations_this_period = np.sum(condition_separation)

    return dataf, separations_this_period

def marriage(dataf):
    """
    10% of all couples get married
    """
    dataf = dataf.copy()

    marriable = (dataf['married'] == 0) & (dataf['in_couple']==1)
    probability = np.random.uniform(0, 1, len(dataf))
    condition = (marriable) & (probability<0.1)

    dataf.loc[condition, 'married'] = 1
    marriages_this_period = np.sum(condition)

    return dataf, marriages_this_period

def sim_birth(dataf, type):
    dataf = dataf.copy()

    if type == 'ext':
        X = data_general(dataf, 'birth', estimate=0)
        predictions = _ext(X, 'birth')
    elif type == 'standard':
        X = data_birth(dataf, estimate=0)
        predictions = _ml(X, 'birth')
    else:
        X = data_birth(dataf, estimate=0)
        predictions = _ml(X, 'birth')


    return predictions

def scale_data(dataf):
    dataf = dataf.copy()

    X = StandardScaler().fit_transform(np.asarray(dataf))
    scaler = 0
    return X, scaler

def make_new_humans(dataf):
    """
    Takes the mother's values and adjust some of them accordingly (setting age=0 for example)
    """
    dataf = dataf.copy()

    df_babies = dataf[dataf['birth'] == 1].copy()
    n_babies = len(df_babies)
    pid_max = dataf['pid'].max()

    pids = np.arange((pid_max+1), (pid_max + n_babies+1))
    df_babies['pid'] = pids
    df_babies['child'] = 1

    gender = np.random.randint(0, 2, size=len(df_babies))
    df_babies['female'] = gender
    df_babies['predicted'] = 1

    settozero = ['age',
                 'gross_earnings',
                 'in_couple',
                 'married',
                 'hours',
                 'education',
                 'employment_status',
                 'fulltime',
                 'lfs',
                 'working',
                 'birth']

    df_babies[settozero] = 0
    return df_babies, n_babies

def birth(dataf):
    """
    Determines who gets children and then generates a new DF containing the old one plus the infants
    """
    dataf = dataf.copy()

    df_possible = dataf[(dataf['female']==1) &  \
                             (dataf['child']==0) & \
                             (15 <= dataf['age']) & \
                             (dataf['age'] <= 49)]

    df_merged = df_possible.merge(fertility, left_on='age', right_on='Age')

    probs = np.random.uniform(size=len(df_possible))
    df_merged['birth'] = 0

    cond = df_merged['1968']/1000 < probs
    df_merged.loc[cond, 'birth']=1
    df_merged.drop(['1968', 'Age'], axis=1, inplace=True)

    dataf_babies = df_merged[df_merged['birth']==1]
    births_this_period = sum(cond)

    dataf_babies, births_this_period = make_new_humans(dataf)

    dataf = pd.concat([dataf, dataf_babies], ignore_index=True)
    return dataf, births_this_period



def _logit(X, variable):
    X= X.copy()

    X_scaled = scale_data(X)
    #X_scaled['const'] = 1
    estimator  = pd.read_pickle(model_path + variable + "_logit")
    pred = estimator.predict(X_scaled)

    pred_scaled = np.zeros(len(pred))
    pred_scaled[pred>0.5] = 1

    return pred_scaled

def _ml(X, variable):
    X = X.copy()

    X_scaled, scaler = scale_data(X)
    estimator = lgb.Booster(model_file = model_path + variable + '_ml.txt')
    pred = estimator.predict(X_scaled)

    pred_scaled = np.zeros(len(pred))
    pred_scaled[pred>0.5] = 1

    return pred_scaled

def _ext(X, variable):
    X = X.copy()

    X_scaled, scaler = scale_data(X)
    estimator = lgb.Booster(model_file = model_path + \
                            variable + '_extended.txt')
    pred = estimator.predict(X_scaled)

    pred_scaled = np.zeros(len(pred))
    pred_scaled[pred>0.5] = 1

    return pred_scaled
