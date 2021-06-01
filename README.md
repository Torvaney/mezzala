# Mezzala
> Models for estimating football (soccer) team-strength


## Install

`pip install mezzala`

## How to use

```python
import mezzala
```

Fitting a Dixon-Coles team strength model:

First, we need to get some data

```python
import itertools
import json
import urllib.request


# Use 2016/17 Premier League data from the openfootball repo
url = 'https://raw.githubusercontent.com/openfootball/football.json/master/2016-17/en.1.json'


response = urllib.request.urlopen(url)
data_raw = json.loads(response.read())

# Reshape the data to just get the matches
data = list(itertools.chain(*[d['matches'] for d in data_raw['rounds']]))

data[0:3]
```




    [{'date': '2016-08-13',
      'team1': 'Hull City AFC',
      'team2': 'Leicester City FC',
      'score': {'ft': [2, 1]}},
     {'date': '2016-08-13',
      'team1': 'Everton FC',
      'team2': 'Tottenham Hotspur FC',
      'score': {'ft': [1, 1]}},
     {'date': '2016-08-13',
      'team1': 'Crystal Palace FC',
      'team2': 'West Bromwich Albion FC',
      'score': {'ft': [0, 1]}}]



### Fitting a model

To fit a model with mezzala, you need to create an "adapter". Adapters are used to connect a model to a data source.

Because our data is a list of dicts, we are going to use a `KeyAdapter`.

```python
adapter = mezzala.KeyAdapter(       # `KeyAdapter` = datum['...']
    home_team='team1',
    away_team='team2',
    home_goals=['score', 'ft', 0],  # Get nested fields with lists of fields
    away_goals=['score', 'ft', 1],  # i.e. datum['score']['ft'][1]
)

# You'll never need to call the methods on an 
# adapter directly, but just to show that it 

# works as expected:
adapter.home_team(data[0])
```




    'Hull City AFC'



Once we have an adapter for our specific data source, we can fit the model:

```python
model = mezzala.DixonColes(adapter=adapter)
model.fit(data)
```




    DixonColes(adapter=KeyAdapter(home_goals=['score', 'ft', 0], away_goals=['score', 'ft', 1], home_team='team1', away_team='team2'), blocks=[TeamStrength(), BaseRate(), HomeAdvantage()])



### Making predictions

By default, you only need to supply the home and away team to get predictions. This should be supplied in the same format as the training data.

`DixonColes` has two methods for making predictions:

* `predict_one` - for predicting a single match
* `predict` - for predicting multiple matches

```python
match_to_predict = {
    'team1': 'Manchester City FC',
    'team2': 'Swansea City FC',
}

scorelines = model.predict_one(match_to_predict)

scorelines[0:5]
```




    [ScorelinePrediction(home_goals=0, away_goals=0, probability=0.02037042831596072),
     ScorelinePrediction(home_goals=0, away_goals=1, probability=0.015935207480444896),
     ScorelinePrediction(home_goals=0, away_goals=2, probability=0.006232830098272064),
     ScorelinePrediction(home_goals=0, away_goals=3, probability=0.0016252553172631187),
     ScorelinePrediction(home_goals=0, away_goals=4, probability=0.0003178477679454554)]



Each of these methods return predictions in the form of `ScorelinePredictions`. 

* `predict_one` returns a list of `ScorelinePredictions`
* `predict` returns a list of `ScorelinePredictions` for each predicted match (i.e. a list of lists)

However, it can sometimes be more useful to have predictions in the form of match _outcomes_. Mezzala exposes the `scorelines_to_outcomes` function for this purpose:

```python
mezzala.scorelines_to_outcomes(scorelines)
```




    {Outcomes('Home win'): OutcomePrediction(outcome=Outcomes('Home win'), probability=0.828760979161171),
     Outcomes('Draw'): OutcomePrediction(outcome=Outcomes('Draw'), probability=0.1096502468599919),
     Outcomes('Away win'): OutcomePrediction(outcome=Outcomes('Away win'), probability=0.061588773978835644)}



### Extending the model

It's possible to fit more sophisticated models with mezzala, using **weights** and **model blocks**

#### Weights

You can weight individual data points by supplying a function (or callable) to the `weight` argument to `DixonColes`:

```python
mezzala.DixonColes(
    adapter=adapter,
    # By default, all data points are weighted equally,
    # which is equivalent to:
    weight=lambda x: 1
)
```




    DixonColes(adapter=KeyAdapter(home_goals=['score', 'ft', 0], away_goals=['score', 'ft', 1], home_team='team1', away_team='team2'), blocks=[TeamStrength(), BaseRate(), HomeAdvantage()])



Mezzala also provides an `ExponentialWeight` for the purpose of time-discounting:

```python
mezzala.DixonColes(
    adapter=adapter,
    weight=mezzala.ExponentialWeight(
        epsilon=-0.0065,               # Decay rate
        key=lambda x: x['days_ago']
    )
)
```

#### Model blocks

Model "blocks" define the calculation and estimation of home and away goalscoring rates.

```python
mezzala.DixonColes(
    adapter=adapter,
    # By default, only team strength and home advantage,
    # is estimated:
    blocks=[
        mezzala.blocks.HomeAdvantage(),
        mezzala.blocks.TeamStrength(),
        mezzala.blocks.BaseRate(),      # Adds "average goalscoring rate" as a distinct parameter
    ]
)
```




    DixonColes(adapter=KeyAdapter(home_goals=['score', 'ft', 0], away_goals=['score', 'ft', 1], home_team='team1', away_team='team2'), blocks=[TeamStrength(), HomeAdvantage(), BaseRate()])



To add custom parameters (e.g. per-league home advantage), you need to add additional model blocks.
