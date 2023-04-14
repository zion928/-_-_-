import numpy as np
from keras.models import Sequential
from keras.layers import Dense
from typing import *

def create_team_evaluator() -> Sequential:
    model = Sequential()
    model.add(Dense(units=64, activation='relu', input_dim=10))
    model.add(Dense(units=32, activation='relu'))
    model.add(Dense(units=1, activation='linear'))
    model.compile(optimizer='adam', loss='mean_squared_error')
    return model

def train_team_evaluator(model: Sequential, x_train: np.ndarray, y_train: np.ndarray, epochs: int = 10):
    model.fit(x_train, y_train, epochs=epochs, verbose=0)

def evaluate_teams(model: Sequential, teams: List[List[Dict[str, Union[str, int]]]]) -> float:
    input_vector = teams_to_input_vector(teams)
    team_fitness = model.predict(np.array([input_vector]))[0][0]
    return team_fitness