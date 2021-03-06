import numpy as np
import pandas as pd
import pickle
from pathlib import Path

import statsmodels.api as sm
from bokeh.layouts import row
from bokeh.plotting import figure, show
from bokeh.models import ColumnDataSource
from bokeh.io import export_png

import sys

###############################################################################
dir = Path(__file__).resolve().parents[2]
current_week = "week" + str(sys.argv[1])

path = dir / "output" / current_week
path.mkdir(parents=True, exist_ok=True)

###############################################################################

def restrict(dataf, female=None):
    
    df_working = dataf[dataf["working_real"]==1]
    
    if female==1:
        df_out = df_working[df_working["female_real"]==1]
    elif female==0:
        df_out = df_working[df_working["female_real"]==0]
    else:
        df_out = df_working
        
    return df_out

def get_unemp(dataf):
    dataf = dataf.copy()
    
    df_out = pd.DataFrame()
    df_out["emp_female"] = dataf[dataf["female_real"]==1].groupby("age_real")["working_real"].mean()
    df_out["n_female"] = dataf[dataf["female_real"]==1].groupby("age_real")["working_real"].count()

    df_out["emp_male"] = dataf[dataf["female_real"]==0].groupby("age_real")["working_real"].mean()
    df_out["n_male"] = dataf[dataf["female_real"]==0].groupby("age_real")["working_real"].count()
    
    return df_out

def group_age(dataf):
    dataf = dataf.copy()
    
    df_out = dataf.groupby("age_real").median()
    df_out["n"] = dataf.groupby("age_real")["pid"].count()
    return df_out

def make_pretty(p):
    p.xgrid.grid_line_color = None
    p.yaxis.minor_tick_line_width=0
    p.xaxis.minor_tick_line_width=0
    
    p.legend.location = "bottom_right"

    return p  


def plot_sample(dataf, str_path, rest=False):
    
    if rest:
        dataf = restrict(dataf)
    else:
        dataf = dataf.copy()
        
    
    ll = dataf.groupby("period_ahead")["pid"].count().values
    x = np.arange(len(ll))
    
    p=figure(title="Number of people by length of observation",
             y_range = (0, 5500))
    p.vbar(x, top=ll)
    
    p = make_pretty(p)
    
    export_png(p, filename=str(path / str_path))
    
def plot_sample_coeff(dataf, str_path):
    
    dataf = dataf.copy()
    dataf_rest = restrict(dataf)
    
    ll = dataf.groupby("period_ahead")["pid"].count().values
    ll_rest = dataf_rest.groupby("period_ahead")["pid"].count().values
    
    ll_coeff = ll_rest/ll
    x = np.arange(len(ll_coeff))
    
    p=figure(title="Fraction of people working by lenght of observation",
             y_range=(0, 1))
    p.vbar(x, top=ll_coeff)
    
    p = make_pretty(p)
    export_png(p, filename=str(path / str_path))

    
def plot_by_age(dataf, str_path, rest=False):
    
    if rest:
        dataf = restrict(dataf)
    else:
        dataf = dataf.copy()
    
    ll = dataf.groupby("age_real")["pid"].count().values
    x = np.arange(len(ll)) + min(dataf["age_real"])
    
    p=figure(title="Number of observed people by age",
             y_range = (0, 2500))
    p.vbar(x, top=ll)
    
    p = make_pretty(p)
    export_png(p, filename=str(path / str_path))
    
def plot_2c(dataf, str_path):
    
    dataf = dataf.copy()
    
    df_group = dataf.groupby("pid")[["working_real", "period_ahead"]]
    
    # Getting mean of working years per person
    work = df_group.mean()["working_real"]
    # Getting max amount of periods we observe a person
    obs = df_group.max()["period_ahead"]
    
    # Concat those two frames
    df_combined = pd.concat([work, obs], axis=1)
    ll_mean = df_combined.groupby("period_ahead").mean().values
    ll_median = df_combined.groupby("period_ahead").median().values
    
    overall_mean = dataf["working_real"].mean()
    
    x = np.arange(len(ll_mean))
    
    source = ColumnDataSource(data={"x": x,
                                    "y_mean": ll_mean,
                                    "y_median": ll_median,
                                    "overall_mean": np.repeat(overall_mean, len(ll_mean))})
    
    p=figure(title="Fraction of working years by length of observation")
    
    p.line(x="x", y="y_mean", source=source,
           line_color="black", line_dash="solid", line_width=3,
           legend_label = "mean")
    
    p.line(x="x", y="y_median", source=source,
        line_color="black", line_dash="dashed", line_width=3,
        legend_label = "median")
    
    p.line(x="x", y="overall_mean", source=source,
        line_color="red", line_dash="solid", line_width=2,
        legend_label = "Overall mean")
    
    p = make_pretty(p)
    export_png(p, filename=str(path/ str_path)) 

# Log profile of wages
def plot_log_wages(dataf):
    dataf = dataf.copy()
    
    vars = ["gross_earnings_real",
            "gross_earnings_standard",
            "gross_earnings_ext"]

    dataf[vars] = np.log(dataf[vars])

    source = ColumnDataSource(dataf)
    p = figure(title="Log earnings by age group")

    p.line(x="age_real", y="gross_earnings_real", source=source,
        line_color="black", line_dash="solid", line_width=3,
        legend_label = "Real")

    p.line(x="age_real", y="gross_earnings_standard", source=source,
        line_color="black", line_dash="dashed", line_width=3,
        legend_label = "Standard")

    p.line(x="age_real", y="gross_earnings_ext", source=source,
        line_color="black", line_dash="dotted", line_width=3,
        legend_label = "Ext")

    export_png(p, filename="plot.png")
    
def get_coeff(y, x):
    y = y.values
    x = x.values
    
    x = sm.add_constant(x)
    
    res = sm.OLS(y, x).fit()
    
    print(res.summary())
    
def get_log_var(dataf, var):
    dataf = dataf.copy()
    
    dataf = dataf[dataf[var] != 0]
    
    dataf["log"] = np.log(dataf[var])
    df_out = dataf.groupby("age_real").var()
    df_out["n"] = dataf.groupby("age_real")["pid"].count()
    
    return df_out[["log", "n"]]
    
    
##############################################################################
df = pd.read_pickle(path / "df_analysis_full")

##############################################################################
# Quick look at sample
# get_unemp(df)


##############################################################################
# Quick look at median gross earnings and hours by age group
# Only for working people now

dataf_rest=restrict(df)
dataf_incomes=group_age(dataf_rest)


dataf_incomes[["gross_earnings_real",
              "gross_earnings_standard",
              "gross_earnings_ext",
              "n"]]

dataf_incomes[["hours_real",
              "hours_standard",
              "hours_ext",
              "n"]]


##############################################################################
# Plot of log wages

# plot_log_wages(dataf_incomes)
##############################################################################
# Autocorrelations - Brenner T2

dataf_rest1 = dataf_rest[np.isin(dataf_rest["age_real"], np.arange(42, 53))]

vars = ["gross_earnings", "hours"]
types = ["real", "standard", "ext"]


v = vars[0]
t = types[2]

print("This are the results with approach:", t, " \n")

variable = v + "_" + t
variable_lag = v + "_t1_" + t

# get_coeff(dataf_rest1[variable], 
#           dataf_rest1[variable_lag])


##############################################################################
# Variance of log earnings - Kopczuk T1
# abc = get_log_var(dataf_rest, variable)

if __name__ == "__main__": 
    plot_2c(df, "fig2c.png")
    plot_sample(df, "sample_duration.png")
    plot_sample(df, "sample_duration_working.png", rest=True)
    plot_sample_coeff(df, "sample_duration_relative.png")
    plot_by_age(df, "sample_age.png")
    plot_by_age(df, "sample_age_working.png", rest=True)


