import pandas as pd
import numpy as np
from  .utils import *

__all__ = ["fom"]

class fom:
    def __init__(self,data,pol_in,input, id = None):
        dataframe = DATA_TO_DF(data, id)
        self.df, self.S_columns = df_filter(dataframe,pol_in,input)
        S_col = [col for col in self.S_columns if col.split("_")[0][1] != col.split("_")[0][2]]
        self.S_col_mag = [c for c in S_col if c.endswith("_magnitude")]

    def magnitude(self):
        df_mag = self.df.copy()
        S_col_mag_1 = [co for co in self.S_columns if co.endswith("_magnitude")]
        df_mag = df_mag[["wavelength", "pol_in", "pol_out"] + S_col_mag_1]
        return df_mag
    
    def phase(self):
        df_phase = self.df.copy()
        S_col_phase = [co for co in self.S_columns if co.endswith("_phase")]
        df_phase = df_phase[["wavelength", "pol_in", "pol_out"] + S_col_phase]
        return df_phase

    def IL(self):
        df_IL = self.df.copy()
        df_IL[self.S_col_mag] = -10 * np.log10(df_IL[self.S_col_mag].astype(float) ** 2)
        df_IL.rename(columns={col: col.replace("_magnitude", "_IL") for col in self.S_col_mag},inplace=True)
        df_IL = df_IL[["wavelength", "pol_in", "pol_out"] +[c for c in df_IL.columns if c.endswith("_IL")]]
        return df_IL
    
    def EL(self):
        df_EL = self.df.copy()
        df_EL["S_EL"] = -10 * np.log10((df_EL[self.S_col_mag].astype(float) ** 2).sum(axis=1))
        df_EL = df_EL[["wavelength", "pol_in", "pol_out"] +[c for c in df_EL.columns if c.startswith("S_EL")]]
        return df_EL
    
    def XT(self):
        # Only valid for structures with k = 1 or k = 0
        df_XT = self.df.copy()
        medias = self.df[self.S_col_mag].mean()
        if medias.iloc[0] < medias.iloc[1]:
            df_XT["S_XT"] = -10*np.log10(df_XT[self.S_col_mag[0]].astype(float)**2)
        else: 
            df_XT["S_XT"] = -10*np.log10(df_XT[self.S_col_mag[1]].astype(float)**2)
        df_XT = df_XT[["wavelength", "pol_in", "pol_out"] +[c for c in df_XT.columns if c.startswith("S_XT")]]
        return df_XT
    
    def IB(self):
        # Only valid for structures with k = 0.5
        df_IB = self.df.copy()
        df_IB["S_IB"] = 20 * np.log10(df_IB[self.S_col_mag[0]].astype(float) / df_IB[self.S_col_mag[1]].astype(float))
        df_IB = df_IB[["wavelength", "pol_in", "pol_out"] +[c for c in df_IB.columns if c.startswith("S_IB")]]
        return df_IB

    

