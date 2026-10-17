from pathlib import Path
import pandas as pd
import fitz
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'reports/assets'
ASSETS.mkdir(parents=True,exist_ok=True)
(ASSETS/'slides').mkdir(exist_ok=True)
df=pd.read_csv(ROOT/'data/processed/faucets_sales_cleaned.csv.zip',parse_dates=['month'])
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.titlesize':17,'axes.titleweight':'bold','text.color':'#14283E','axes.labelcolor':'#526174','axes.edgecolor':'#D6DFE7','axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white','axes.facecolor':'white','savefig.facecolor':'white'})
NAVY='#14283E';GREEN='#23856E';BLUE='#477FC1';GREY='#607286'
def save(fig,name):
 fig.savefig(ASSETS/name,dpi=150,bbox_inches='tight',pad_inches=.3);plt.close(fig)
fig=plt.figure(figsize=(13,4.4))
fig.text(.03,.88,'АНАЛИЗ РЫНКА КУХОННЫХ СМЕСИТЕЛЕЙ',fontsize=23,fontweight='bold')
fig.text(.03,.77,'Данные о продажах → конкурентный анализ → стратегия выхода',fontsize=14,color=GREY)
for i,(v,l) in enumerate([('218 668','записей после очистки'),('3,28 млрд ₽','выручка в данных за 2024'),('+28,8%','рост выручки год к году'),('2 страницы','интерактивного Power BI')]):
 x=.03+i*.245;fig.text(x,.45,v,fontsize=25,fontweight='bold',color=GREEN);fig.text(x,.33,l,fontsize=11,color=GREY)
fig.text(.03,.1,'Учебный командный проект  |  Python · Power BI · Excel  |  Период данных: 2023–2024',fontsize=11,color=GREY)
save(fig,'project_overview.png')
m=df.groupby(['year',df.month.dt.month]).revenue.sum().unstack(0)/1e6
fig,ax=plt.subplots(figsize=(12.4,5.3))
for y,c in [(2023,BLUE),(2024,GREEN)]:ax.plot(range(1,13),m[y],marker='o',lw=2.7,ms=6,color=c,label=str(y))
ax.set_xticks(range(1,13),['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек'])
ax.set_ylim(70,370);ax.set_ylabel('Выручка, млн руб.');ax.grid(axis='y',alpha=.16);ax.legend(ncol=2,frameon=False,loc='upper left')
ax.set_title('Рост выручки +28,8% при росте продаж в штуках +27,6%',loc='left',pad=22)
fig.text(.1,.005,'Максимальная месячная выручка в обоих годах — в декабре. Источник: очищенный набор.',fontsize=10,color=GREY)
save(fig,'market_dynamics.png')
order=['Бюджетный','Средний','Премиум','Люкс']
s=df.groupby('price_segment').revenue.sum().reindex(order)/df.revenue.sum()*100
fig,ax=plt.subplots(figsize=(12.4,4.8))
bars=ax.barh(order,s,color=['#B9CFDB','#8AB7BE','#529B98',GREEN],height=.58)
ax.invert_yaxis();ax.set_xlim(0,39);ax.set_xlabel('Доля выручки за 2023–2024 годы, %')
ax.set_title('Верхние две ценовые группы дают 59,7% выручки',loc='left',pad=22)
for b,v in zip(bars,s):ax.text(v+.5,b.get_y()+b.get_height()/2,f'{v:.1f}%'.replace('.',','),va='center',fontweight='bold')
ax.grid(axis='x',alpha=.12);ax.set_axisbelow(True)
fig.subplots_adjust(bottom=.23)
fig.text(.09,.025,'Квартильные границы: 2 301 / 3 999 / 7 516,25 руб. Около 25% строк в каждой группе.',fontsize=10,color=GREY)
save(fig,'price_segments.png')
annual=df.groupby(['brand_clean','year']).revenue.sum().unstack(fill_value=0)
named=annual.drop('NoName/Прочие').sort_values(2024,ascending=False).head(10)
chosen=annual.loc[['Accoona','Shevanik','Wasserberg','Dionis','Shimizu']]
growth=((chosen[2024]/chosen[2023]-1)*100).sort_values(ascending=False)
fig,(a,b)=plt.subplots(1,2,figsize=(14,6.2),gridspec_kw={'width_ratios':[1.15,1]})
a.barh(named.index,named[2024]/1e6,color=BLUE,height=.65);a.invert_yaxis();a.set_xlim(0,180);a.set_xlabel('млн руб.')
a.set_title('Лидеры по выручке в 2024 году',loc='left',pad=22,fontsize=15)
for i,v in enumerate(named[2024]/1e6):a.text(v+1.4,i,f'{v:.1f}'.replace('.',','),va='center',fontsize=10)
b.barh(growth.index,growth,color=GREEN,height=.55);b.invert_yaxis();b.set_xlim(0,475);b.set_xlabel('2024 / 2023, %')
b.set_title('Рост выбранных конкурентов',loc='left',pad=22,fontsize=15)
for i,v in enumerate(growth):b.text(v+6,i,f'+{v:.1f}%'.replace('.',','),va='center',fontsize=11)
for ax in (a,b):ax.grid(axis='x',alpha=.12);ax.set_axisbelow(True)
fig.subplots_adjust(wspace=.48,bottom=.15)
fig.text(.08,.025,'Слева — именованные бренды без NoName. Справа — примеры среди лидеров суммарного рейтинга.',fontsize=10,color=GREY)
save(fig,'competitor_analysis.png')
abc=df.groupby('brand_abc').agg(brands=('brand_clean','nunique'),revenue=('revenue','sum')).reindex(['A','B','C'])
fig,(a,b)=plt.subplots(1,2,figsize=(12.4,4.5))
a.bar(['A','B','C'],abc.brands,color=[GREEN,BLUE,'#9CB0C0'],width=.5);a.set_ylim(0,1120)
a.set_title('Количество брендов / групп',loc='left',pad=20,fontsize=15)
for i,v in enumerate(abc.brands):a.text(i,v+15,str(v),ha='center',fontweight='bold')
s=abc.revenue/abc.revenue.sum()*100
b.bar(['A','B','C'],s,color=[GREEN,BLUE,'#9CB0C0'],width=.5);b.set_ylim(0,95)
b.set_title('Доля в выручке, %',loc='left',pad=20,fontsize=15)
for i,v in enumerate(s):b.text(i,v+2,f'{v:.1f}%'.replace('.',','),ha='center',fontweight='bold')
for ax in (a,b):ax.grid(axis='y',alpha=.12);ax.set_axisbelow(True)
fig.subplots_adjust(wspace=.25,bottom=.17)
fig.text(.08,.02,'Суммарная выручка за два года. Границы накопленной доли: 80% и 95%.',fontsize=10,color=GREY)
save(fig,'abc_analysis.png')
doc=fitz.open(ROOT/'reports/faucets_market_entry_presentation.pdf')
for n,name,clip in [(8,'dashboard_market.png',(500,170,1845,1065)),(11,'dashboard_positioning.png',(532,170,1855,1055))]:
 doc[n-1].get_pixmap(matrix=fitz.Matrix(1.7,1.7),clip=fitz.Rect(*clip),alpha=False).save(ASSETS/name)
for i,page in enumerate(doc):
 (ASSETS/f'slides/slide_{i+1:02}.jpg').write_bytes(page.get_pixmap(matrix=fitz.Matrix(1,1),alpha=False).tobytes('jpeg',jpg_quality=88))
print('Created 5 overview/analysis images, 2 dashboards, 22 slides')

