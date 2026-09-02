from .utils import _cm_json_to_dict, df_filter, DATA_TO_DF
from .fom import *
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio

__all__ = ["visualizer"]

'''
If only want to visualize 1 component, 
'''
pio.renderers.default = "vscode"
class visualizer:
    def __init__(self, data, pol_in, input, id=None):
        self.components = {}
        flag = False
        while flag == False:
            if isinstance(id,list):
                for id_val in id:
                    try:
                        dataframe = DATA_TO_DF(data, id_val)
                        df, S_columns = df_filter(dataframe,pol_in,input)
                        # Data must have been validated to be BBinstances.json
                        description = _cm_json_to_dict(file=data, target_id= id_val,visualizer = 1)
                        self.components[id_val] = {
                        "df": df,
                        "description": description
                        }
                    except ValueError:
                        print(f"ID no encontrado: {id_val}")
                flag = True
            else:
                id = [id]
            
        self.id = id
        self.file = data  
        self.pol_in = pol_in
        self.input = input

        if not self.components:
            raise ValueError("No se pudo cargar ningún ID válido")

    def plot(self, plot=None):
        all_dfs = []
        for id_val, comp in self.components.items():
            df = comp["df"]
            fom_obj = fom(data = df, pol_in = self.pol_in, input = self.input,id = self.id)
            if plot == str('magnitude'):
                df_plot = df[["wavelength", "pol_in", "pol_out"] +[c for c in df.columns if c.endswith("magnitude")]]
                y_axis = 'Magnitude'
            elif plot == str('phase'):
                df_plot = df[["wavelength", "pol_in", "pol_out"] +[c for c in df.columns if c.endswith("phase")]]
                y_axis = 'Phase'
            elif plot == str('IL'):
                df_plot = fom_obj.IL()
                y_axis = 'Insertion losses (dB)'
            elif plot == str('EL'):
                df_plot = fom_obj.EL()
                y_axis = 'Excess loss (dB)'
            elif plot == str('XT'):
                df_plot = fom_obj.XT()
                y_axis = 'Crosstalk (dB)'
            elif plot == str('IB'):
                df_plot = fom_obj.IB()
                y_axis = 'Imbalance (dB)'
            else:
                raise ValueError('Error. Function plot only accepts: magnitude, phase, IL, EL, XT, IB')

            df_plot["component_id"] = id_val
            all_dfs.append(df_plot)

        full_df = pd.concat(all_dfs, ignore_index=True)
        ids = list(self.components.keys())
        descriptions = [self.components[i]["description"] for i in ids]
        S_columns = [col for col in full_df.columns if col.startswith("S")]
        n_rows = len(ids)
        n_cols = len(S_columns)

        fig = make_subplots(rows=n_rows,cols=n_cols,shared_xaxes=False,subplot_titles=S_columns* n_rows)

        # Color map for each polarization
        pols = sorted(full_df["pol_out"].unique())
        default_colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728","#9467bd", "#8c564b", "#e377c2", "#7f7f7f","#bcbd22", "#17becf"]
        color_map = {
            pol: default_colors[i % len(default_colors)]
            for i, pol in enumerate(pols)
        }
        shown = set()

        # Title for every component
        for i, desc in enumerate(descriptions):
            y_domain = fig.layout[f'yaxis{1 + i*n_cols}'].domain
            y_top = y_domain[1]
            fig.add_annotation(text=f"<b>{desc}</b>",x=0.5,y=y_top+0.1,xref="paper",yref="paper",showarrow=False,font=dict(size=16))

        # plot
        for i, comp_id in enumerate(ids, start=1):
            df_id = full_df[full_df["component_id"] == comp_id]
            for j, S_col in enumerate(S_columns, start=1):
                grouped = df_id.groupby("pol_out")
                for pol, group in grouped:
                    # TM plot with scatter
                    is_tm = "TM" in str(pol)
                    if is_tm:
                        n_points = len(group)
                        if n_points < 200:
                            step = 1
                        elif n_points < 1000:
                            step = 5
                        else:
                            step = 10
                        group_plot = group.iloc[::step]
                        mode = "lines+markers"
                        marker = dict(size=4)
                    # TE plot with lines
                    else:
                        group_plot = group
                        mode = "lines"
                        marker = None
                    line = dict(color=color_map[pol],width=2)
                    show = pol not in shown
                    shown.add(pol)

                    fig.add_trace(
                        go.Scatter(x=group_plot["wavelength"],y=group_plot[S_col],mode=mode,name=str(pol),legendgroup=str(pol),line=line,marker=marker,showlegend=show
                        ),
                        row=i,
                        col=j
                    )
                fig.update_xaxes(title_text="Wavelength (nm)", row=i, col=j)
                if j == 1:
                    fig.update_yaxes(title_text=y_axis, row=i, col=j)
        fig.update_layout(height=300 * n_rows,width=400 * n_cols,title="Interactive S-parameters visualization",hovermode="x unified",legend=dict(title=dict(text="pol_out")))
        fig.show(renderer="notebook_connected")
