import os
import numpy as np
import pandas as pd
import pickle

import statsmodels.api as sm
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, GridSearchCV


import lightgbm as lgb
from sklearn.linear_model import LogisticRegression, LinearRegression

input_path = "/Users/christianhilscher/Desktop/dynsim/input/"
model_path = "/Users/christianhilscher/desktop/dynsim/src/estimation/modelsWA_CV/"

def getdf(dataf):
    dataf = dataf.copy()

    condition = dataf.groupby('pid')['year'].count()>2
    dataf = dataf.set_index('pid')[condition]
    year_list = dataf['year'].unique()

    dataf['hours_t1'] = np.NaN
    dataf['gross_earnings_t1'] = np.NaN

    dataf_out = pd.DataFrame()
    for i in np.sort(year_list)[2:]:
        df_now = dataf[dataf['year'] == i].copy()
        df_yesterday = dataf[dataf['year'] == (i-1)].copy()
        df_twoyesterdays = dataf[dataf['year'] == (i-2)].copy()

        df_now['retired_t1'] = df_yesterday['retired']
        df_now['working_t1'] = df_yesterday['working']
        df_now['fulltime_t1'] = df_yesterday['fulltime']
        df_now['hours_t1'] = df_yesterday['hours']
        df_now['hours_t2'] = df_twoyesterdays['hours']
        df_now['gross_earnings_t1'] = df_yesterday['gross_earnings']
        df_now['gross_earnings_t2'] = df_twoyesterdays['gross_earnings']
        df_now['employment_status_t1'] = df_yesterday['employment_status']
        df_now['employment_status_t2'] = df_twoyesterdays['employment_status']

        dataf_out = pd.concat([dataf_out, df_now])

    dataf_out.reset_index(inplace=True)
    dataf_out.dropna(inplace=True)
    return dataf_out

def get_dependent_var(dataf, dep_var):
    dataf = dataf.copy()

    dataf.rename(columns={dep_var: 'dep_var'}, inplace=True)
    return dataf

def _prepare_classifier(dataf):
    dataf = dataf.copy()

    y = dataf['dep_var']
    X = dataf.drop('dep_var', axis=1)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size = 0.05)

    # Making weights
    weights_train = X_train['personweight']
    X_train.drop('personweight', axis=1, inplace=True)


    weights_test = X_test['personweight']
    X_test.drop('personweight', axis=1, inplace=True)


    if "personweight_interacted" in X.columns.tolist():
        X_train.drop('personweight_interacted', axis=1, inplace=True)
        X_test.drop('personweight_interacted', axis=1, inplace=True)
    else:
        pass

    # Scaling
    X_train_scaled = StandardScaler().fit_transform(np.asarray(X_train))
    X_test_scaled = StandardScaler().fit_transform(np.asarray(X_test))

    # Coeffs feature_names
    feature_names = X_train.columns.tolist()

    # For Standard Part:
    X_train = sm.add_constant(X_train)
    X_test = sm.add_constant(X_test)

    # For ML part:
    lgb_train = lgb.Dataset(X_train_scaled, y_train,
                            weight = weights_train)
    lgb_test = lgb.Dataset(X_test_scaled, y_test,
                           weight = weights_test)

    out_dici = {'X_train': X_train_scaled,
                'X_test': X_test_scaled,
                'y_train': y_train,
                'y_test': y_test,
                'lgb_train': lgb_train,
                'lgb_test': lgb_test,
                'features': feature_names,
                'weights': weights_train}
    return out_dici

def _prepare_regressor(dataf):
    dataf = dataf.copy()

    y = dataf['dep_var']
    X = dataf.drop('dep_var', axis=1)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size = 0.05)

    # Making weights
    weights_train = X_train['personweight']
    X_train.drop('personweight', axis=1, inplace=True)

    weights_test = X_test['personweight']
    X_test.drop('personweight', axis=1, inplace=True)

    # Scaling
    X_train_scaled = StandardScaler().fit_transform(np.asarray(X_train))
    X_test_scaled = StandardScaler().fit_transform(np.asarray(X_test))
    y_train_scaled = StandardScaler().fit_transform(np.asarray(y_train).reshape(-1,1))

    # Saving the scaler of the test data to convert the predicted values again
    y_test_scaler = StandardScaler().fit(np.asarray(y_test).reshape(-1,1))
    y_test_scaled = y_test_scaler.transform(np.asarray(y_test).reshape(-1,1))

    feature_names = X_train.columns.tolist()
    y_test_scaled = np.ravel(y_test_scaled)
    y_train_scaled = np.ravel(y_train_scaled)

    # For Standard Part:
    X_train = sm.add_constant(X_train)
    X_test = sm.add_constant(X_test)

    # For ML part:
    lgb_train = lgb.Dataset(X_train_scaled, y_train,
                            weight = weights_train)
    lgb_test = lgb.Dataset(X_test_scaled, y_test,
                           weight = weights_test)


    out_dici = {'X_train': X_train_scaled,
                'X_test': X_test,
                'y_train': y_train_scaled,
                'y_test': y_test,
                'scaler': y_test_scaler,
                'lgb_train': lgb_train,
                'lgb_test': lgb_test,
                'features': feature_names,
                'weights': weights_train}
    return out_dici

def _interact(dataf, estimate):
    dataf = dataf.copy()

    names = dataf.columns.tolist()
    if estimate==1:
        names.remove('dep_var')
    else:
        pass

    if "female" in names:
        names.remove('female')
    else:
        pass

    for name in names:
        df_tmp = np.multiply(dataf[name],dataf['female'])
        var_name = name + "_interacted"
        dataf[var_name] = df_tmp
    return dataf

def _age_squared(dataf):
    dataf = dataf.copy()
    dataf['age_squared'] = dataf['age'].astype('long')**2
    return dataf

def _add_constant(dataf):
    dataf = dataf.copy()
    dataf = sm.add_constant(dataf)
    return dataf


#############################################################################
#############################################################################
##############################################################################
def data_birth(dataf, estimate=1):
    dataf = dataf.copy()
    dataf = dataf[(dataf['female']==1) & (dataf['child']==0)]

    if estimate == 1:
        dataf= get_dependent_var(dataf, 'birth')
        vars_retain = ['dep_var',
                       'education',
                       'age',
                       'married',
                       'n_children',
                       'hh_youngest_age',
                       'personweight']
    elif estimate == 0:
        vars_retain = ['education',
                       'age',
                       'married',
                       'n_children',
                       'hh_youngest_age']
    else:
        raise ValueError("0 is for simulation, 1 for estimation")

    dataf = dataf[vars_retain]
    #dataf = _interact(dataf,estimate)
    return dataf

def estimate_birth(dataf):
    dataf = dataf.copy()

    dataf = data_birth(dataf)
    dataf.dropna(inplace=True)
    dict = _prepare_classifier(dataf)

    model = LogisticRegression(C=1e9)
    logit = model.fit(dict['X_train'], dict['y_train'],
              sample_weight=dict['weights'])

    estimator = lgb.LGBMRegressor(num_leaves = 31)
    modl = estimator.fit(dict['X_train'], dict['y_train'],
                  eval_set=[(dict['X_test'], dict['y_test'])],
                  feature_name = dict['features'],
                  eval_metric = 'logloss',
                  early_stopping_rounds = 5)

    param_grid = {
        'learning_rate': np.linspace(0.01, 1, 7),
        'n_estimators': [150, 200, 250],
        'boosting_type': ['gbdt', 'rf', 'dart'],
        'feature_fraction': [0.9],
        'bagging_fraction': [0.8],
        'bagging_freq': [5]
    }

    cvmodl = GridSearchCV(modl, param_grid, cv=3, verbose=5, n_jobs=-1)
    cvmodl.fit(dict['X_train'], dict['y_train'])

    ml = cvmodl.best_estimator_.booster_

    pickle.dump(logit,
                open(model_path + "birth_logit", 'wb'))
    ml.save_model(model_path + "birth_ml.txt")


def data_retired(dataf, estimate=1):
    dataf = dataf.copy()

    if estimate == 1:
        dataf= get_dependent_var(dataf, 'retired')
        vars_retain = ['dep_var',
                       'retired_t1',
                       'working_t1',
                       'n_children',
                       'hh_youngest_age',
                       'hh_income',
                       'hh_frac_working',
                       'female',
                       'age',
                       'personweight']
    elif estimate == 0:
        vars_retain = ['retired_t1',
                       'working_t1',
                       'n_children',
                       'hh_youngest_age',
                       'hh_income', 'hh_frac_working',
                       'female',
                       'age']
    else:
        raise ValueError("0 is for simulation, 1 for estimation")


    dataf = dataf[vars_retain]
    dataf = _interact(dataf,estimate)
    dataf = _age_squared(dataf)

    return dataf

def estimate_retired(dataf):
    dataf = dataf.copy()

    dataf = data_retired(dataf)
    dataf.dropna(inplace=True)
    dict = _prepare_classifier(dataf)

    model = LogisticRegression(C=1e9)
    logit = model.fit(dict['X_train'], dict['y_train'],
              sample_weight=dict['weights'])

    estimator = lgb.LGBMRegressor(num_leaves = 31)
    modl = estimator.fit(dict['X_train'], dict['y_train'],
                  eval_set=[(dict['X_test'], dict['y_test'])],
                  feature_name = dict['features'],
                  eval_metric = 'logloss',
                  early_stopping_rounds = 5)

    param_grid = {
        'learning_rate': np.linspace(0.01, 1, 7),
        'n_estimators': [150, 200, 250],
        'boosting_type': ['gbdt', 'rf', 'dart'],
        'feature_fraction': [0.9],
        'bagging_fraction': [0.8],
        'bagging_freq': [5]
    }

    cvmodl = GridSearchCV(modl, param_grid, cv=3, verbose=5, n_jobs=-1)
    cvmodl.fit(dict['X_train'], dict['y_train'])

    ml = cvmodl.best_estimator_.booster_
    ml.save_model(model_path + "retired_ml.txt")

    pickle.dump(logit,
                open(model_path + "retired_logit", 'wb'))

def data_working(dataf, estimate=1):
    dataf = dataf.copy()
    dataf = dataf[dataf['retired']==0]


    if estimate == 1:
        dataf= get_dependent_var(dataf, 'working')
        vars_retain = ['dep_var',
                       'fulltime_t1',
                       'working_t1',
                       'n_children',
                       'hh_youngest_age',
                       'hh_income',
                       'hh_frac_working',
                       'female',
                       'age',
                       'personweight']
    elif estimate == 0:
        vars_retain = ['fulltime_t1',
                       'working_t1',
                       'n_children',
                       'hh_youngest_age',
                       'hh_income', 'hh_frac_working',
                       'female',
                       'age']
    else:
        raise ValueError("0 is for simulation, 1 for estimation")

    dataf = dataf[vars_retain]
    dataf = _interact(dataf,estimate)
    dataf = _age_squared(dataf)

    return dataf

def estimate_working(dataf):
    dataf = dataf.copy()

    dataf = data_working(dataf)
    dataf.dropna(inplace=True)
    dict = _prepare_classifier(dataf)

    model = LogisticRegression(C=1e9)
    logit = model.fit(dict['X_train'], dict['y_train'],
              sample_weight=dict['weights'])
    estimator = lgb.LGBMRegressor(num_leaves = 31)
    modl = estimator.fit(dict['X_train'], dict['y_train'],
                  eval_set=[(dict['X_test'], dict['y_test'])],
                  feature_name = dict['features'],
                  eval_metric = 'logloss',
                  early_stopping_rounds = 5)

    param_grid = {
        'learning_rate': np.linspace(0.01, 1, 7),
        'n_estimators': [150, 200, 250],
        'boosting_type': ['gbdt', 'rf', 'dart'],
        'feature_fraction': [0.9],
        'bagging_fraction': [0.8],
        'bagging_freq': [5]
    }

    cvmodl = GridSearchCV(modl, param_grid, cv=3, verbose=5, n_jobs=-1)
    cvmodl.fit(dict['X_train'], dict['y_train'])

    ml = cvmodl.best_estimator_.booster_

    pickle.dump(logit,
                open(model_path + "working_logit", 'wb'))
    ml.save_model(model_path + "working_ml.txt")

def data_fulltime(dataf, estimate=1):
    dataf = dataf.copy()
    dataf = dataf[dataf['working']==1]


    if estimate == 1:
        dataf= get_dependent_var(dataf, 'fulltime')
        vars_retain = ['dep_var',
                       'fulltime_t1',
                       'working_t1',
                       'n_children',
                       'hh_youngest_age',
                       'hh_income',
                       'hh_frac_working',
                       'female',
                       'age',
                       'personweight']
    elif estimate == 0:
        vars_retain = ['fulltime_t1',
                       'working_t1',
                       'n_children',
                       'hh_youngest_age',
                       'hh_income', 'hh_frac_working',
                       'female',
                       'age']
    else:
        raise ValueError("0 is for simulation, 1 for estimation")

    dataf = dataf[vars_retain]
    dataf = _interact(dataf,estimate)
    dataf = _age_squared(dataf)

    return dataf

def estimate_fulltime(dataf):
    dataf = dataf.copy()

    dataf = data_fulltime(dataf)
    dataf.dropna(inplace=True)
    dict = _prepare_classifier(dataf)


    model = LogisticRegression(C=1e9)
    logit = model.fit(dict['X_train'], dict['y_train'],
              sample_weight=dict['weights'])
    estimator = lgb.LGBMRegressor(num_leaves = 31)
    modl = estimator.fit(dict['X_train'], dict['y_train'],
                  eval_set=[(dict['X_test'], dict['y_test'])],
                  feature_name = dict['features'],
                  eval_metric = 'logloss',
                  early_stopping_rounds = 5)

    param_grid = {
        'learning_rate': np.linspace(0.01, 1, 7),
        'n_estimators': [150, 200, 250],
        'boosting_type': ['gbdt', 'rf', 'dart'],
        'feature_fraction': [0.9],
        'bagging_fraction': [0.8],
        'bagging_freq': [5]
    }

    cvmodl = GridSearchCV(modl, param_grid, cv=3, verbose=5, n_jobs=-1)
    cvmodl.fit(dict['X_train'], dict['y_train'])

    ml = cvmodl.best_estimator_.booster_
    pickle.dump(logit,
                open(model_path + "fulltime_logit", 'wb'))
    ml.save_model(model_path + "fulltime_ml.txt")

def data_hours(dataf, estimate=1):
    dataf = dataf.copy()
    dataf = dataf[dataf['working']==1]


    if estimate == 1:
        dataf= get_dependent_var(dataf, 'hours')
        vars_retain = ['dep_var',
                       'hours_t1',
                       'hours_t2',
                       'fulltime',
                       'fulltime_t1',
                       'gross_earnings_t1',
                       'n_children',
                       'hh_youngest_age',
                       'hh_income',
                       'hh_frac_working',
                       'female',
                       'age',
                       'personweight']
    elif estimate == 0:
        vars_retain = ['hours_t1',
                       'hours_t2',
                       'fulltime',
                       'fulltime_t1',
                       'gross_earnings_t1',
                       'n_children',
                       'hh_youngest_age',
                       'hh_income',
                       'hh_frac_working',
                       'female',
                       'age']
    else:
        raise ValueError("0 is for simulation, 1 for estimation")

    dataf = dataf[vars_retain]
    dataf = _age_squared(dataf)

    return dataf

def estimate_hours(dataf):
    dataf = dataf.copy()

    dataf = data_hours(dataf)
    dataf.dropna(inplace=True)
    dict = _prepare_regressor(dataf)

    model = LinearRegression()
    ols = model.fit(dict['X_train'], dict['y_train'],
              sample_weight=dict['weights'])

    estimator = lgb.LGBMRegressor(num_leaves = 31)
    modl = estimator.fit(dict['X_train'], dict['y_train'],
                  eval_set=[(dict['X_test'], dict['y_test'])],
                  feature_name = dict['features'],
                  eval_metric = 'l2',
                  early_stopping_rounds = 5)

    param_grid = {
        'learning_rate': np.linspace(0.01, 1, 7),
        'n_estimators': [150, 200, 250],
        'boosting_type': ['gbdt', 'rf', 'dart'],
        'feature_fraction': [0.9],
        'bagging_fraction': [0.8],
        'bagging_freq': [5]
    }

    cvmodl = GridSearchCV(modl, param_grid, cv=3, verbose=5, n_jobs=-1)
    cvmodl.fit(dict['X_train'], dict['y_train'])

    ml = cvmodl.best_estimator_.booster_

    pickle.dump(ols,
                open(model_path + "hours_ols", 'wb'))
    ml.save_model(model_path + "hours_ml.txt")
    pickle.dump(dict['scaler'],
                open(model_path + "hours_scaler", 'wb'))

def data_earnings(dataf, estimate=1):
    dataf = dataf.copy()
    dataf = dataf[dataf['working']==1]


    if estimate == 1:
        dataf= get_dependent_var(dataf, 'gross_earnings')
        vars_retain = ['dep_var',
                       'gross_earnings_t1',
                       'gross_earnings_t2',
                       'fulltime',
                       'hours',
                       'education',
                       'n_children',
                       'hh_youngest_age',
                       'hh_income',
                       'hh_frac_working',
                       'female',
                       'age',
                       'personweight']
    elif estimate == 0:
        vars_retain = ['gross_earnings_t1',
                       'gross_earnings_t2',
                       'fulltime',
                       'hours',
                       'education',
                       'n_children',
                       'hh_youngest_age',
                       'hh_income', 'hh_frac_working',
                       'female',
                       'age']
    else:
        raise ValueError("0 is for simulation, 1 for estimation")

    dataf = dataf[vars_retain]
    dataf = _age_squared(dataf)

    return dataf

def estimate_earnings(dataf):
    dataf = dataf.copy()

    dataf = data_earnings(dataf)
    dataf.dropna(inplace=True)
    dict = _prepare_regressor(dataf)

    model = LinearRegression()
    ols = model.fit(dict['X_train'], dict['y_train'],
              sample_weight=dict['weights'])

    estimator = lgb.LGBMRegressor(num_leaves = 31)
    modl = estimator.fit(dict['X_train'], dict['y_train'],
                  eval_set=[(dict['X_test'], dict['y_test'])],
                  feature_name = dict['features'],
                  eval_metric = 'l2',
                  early_stopping_rounds = 5)

    param_grid = {
        'learning_rate': np.linspace(0.01, 1, 7),
        'n_estimators': [150, 200, 250],
        'boosting_type': ['gbdt', 'rf', 'dart'],
        'feature_fraction': [0.9],
        'bagging_fraction': [0.8],
        'bagging_freq': [5]
    }

    cvmodl = GridSearchCV(modl, param_grid, cv=3, verbose=5, n_jobs=-1)
    cvmodl.fit(dict['X_train'], dict['y_train'])

    ml = cvmodl.best_estimator_.booster_

    pickle.dump(ols,
                open(model_path + "gross_earnings_ols", 'wb'))
    ml.save_model(model_path + "gross_earnings_ml.txt")
    pickle.dump(dict['scaler'],
                open(model_path + "gross_earnings_scaler", 'wb'))


###############################################################################
if __name__ == "__main__":
    df = pd.read_pickle(input_path + 'workingage').dropna()
    df1 = getdf(df)

    estimate_retired(df1)
    estimate_working(df1)
    estimate_fulltime(df1)
    estimate_hours(df1)
    estimate_earnings(df1)
    estimate_birth(df1)
