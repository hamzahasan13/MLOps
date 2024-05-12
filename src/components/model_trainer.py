import os
import sys
import pandas as pd
from dataclasses import dataclass
import sklearn
import mlflow
import mlflow.sklearn
import mlflow.pyfunc
from mlflow.tracking import MlflowClient
from mlflow.utils.environment import _mlflow_conda_env
from mlflow.tracking import MlflowClient
from mlflow.entities import ViewType
import cloudpickle
from hyperopt import hp
import numpy as np
import time
import pickle

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.ensemble import (
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.linear_model import LinearRegression, ElasticNet
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from sklearn.tree import DecisionTreeRegressor
from sklearn.model_selection import train_test_split

from src.exception import CustomException
from src.logger import logging

from src.utils import save_obj, evaluate_models
from src.components.data_transformation import DataTransformationConfig


class SklearnModelWrapper(mlflow.pyfunc.PythonModel):
    def __init__(self, model):
        self.model = model
    
    def predict(self, context, model_input):
        return self.model.predict(model_input)
@dataclass
class ModelTrainerConfig:
    trained_model_file_path=os.path.join("artifacts", "model.pkl")

class ModelTrainer:
    def __init__(self):
        
        self.model_trainer_config=ModelTrainerConfig()
        self.data_transformation_config = DataTransformationConfig()


    def initiate_model_trainer(self, train_array, test_array, input_feature_train_df, input_feature_test_df):
        try:
            

            logging.info("Split training and test input data")
            X_train, y_train, X_test, y_test = (
                train_array.iloc[:, :-1],
                train_array.iloc[:, -1],
                test_array.iloc[:, :-1],
                test_array.iloc[:, -1]
            )
            
            
            X_orig = pd.concat([input_feature_train_df, input_feature_test_df]).reset_index(drop=True)
            
            models = {
                'Linear Regression': LinearRegression(),
                'Elastic Net': ElasticNet(),
                'Decision Tree Regressor': DecisionTreeRegressor(),
                'RandomForestRegressor': RandomForestRegressor(),
                'GradientBoostingRegressor': GradientBoostingRegressor(),
                'ExtraTreesRegressor': ExtraTreesRegressor(),

            }
            """
            hyperparameters = {
                'Linear Regression': {},  # Linear Regression doesn't have any hyperparameters
                'Elastic Net': {
                    'alpha': [0.001, 0.01, 0.1, 1, 10, 100],
                    'l1_ratio': [0.1, 0.3, 0.5, 0.7, 0.9],
                    'max_iter': [100, 1000, 10000],
                    'tol': [0.0001, 0.001, 0.01, 0.1]
                },
                'Decision Tree Regressor': {
                    'criterion': ['mse', 'friedman_mse', 'mae'],
                    'splitter': ['best', 'random'],
                    'max_depth': [None, 10, 50, 100, 200],
                    'min_samples_split': [2, 5, 10],
                    'min_samples_leaf': [1, 2, 4]
                },
                'RandomForestRegressor': {
                    'n_estimators': [10, 50, 100, 200],
                    'criterion': ['mse', 'mae'],
                    'max_depth': [None, 10, 50, 100, 200],
                    'min_samples_split': [2, 5, 10],
                    'min_samples_leaf': [1, 2, 4],
                    'bootstrap': [True, False]
                },
                'GradientBoostingRegressor': {
                    'loss': ['ls', 'lad', 'huber', 'quantile'],
                    'learning_rate': [0.001, 0.01, 0.1],
                    'n_estimators': [10, 50, 100, 200],
                    'subsample': [0.5, 0.75, 1.0],
                    'max_depth': [3, 4, 5, 6],
                    'min_samples_split': [2, 5, 10],
                    'min_samples_leaf': [1, 2, 4],
                    'alpha': [0.9, 0.99]
                },
                'ExtraTreesRegressor': {
                    'n_estimators': [10, 50, 100, 200],
                    'criterion': ['mse', 'mae'],
                    'max_depth': [None, 10, 50, 100, 200],
                    'min_samples_split': [2, 5, 10],
                    'min_samples_leaf': [1, 2, 4],
                    'bootstrap': [True, False]
                }
            }
            """
            
            model_report:dict=evaluate_models(X_train= X_train, y_train= y_train, X_test= X_test, y_test= y_test, models= models)
        
            ## To get best model score from dict
            best_model_score = max(sorted(model_report.values()))

            ## To get best model name from dict

            best_model_name = list(model_report.keys())[
                list(model_report.values()).index(best_model_score)
            ]
            best_model = models[best_model_name]

            if best_model_score<0.6:
                raise CustomException("No best model found")
            logging.info(f"Best found model on both training and testing dataset")
            
            save_obj(
                file_path=self.model_trainer_config.trained_model_file_path,
                obj=best_model
            )
            
            #MLFLOW_TRACKING_URI = "sqlite:///mlflow.db"

            

            #for run in runs:
            #    print(f"run id: {run.info.run_id}, r2: {run.data.metrics['r2']:.4f}")

            ## Interacting with Model Registry
            
            #mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
            
            """
            loaded_model = pickle.load(open('artifacts/model.pkl', "rb"));
            
            mlflow.set_tracking_uri("sqlite:///mlruns.db")
            reg_model_name = best_model_name
            print("--")
            mlflow.sklearn.log_model(
                loaded_model,
                "sk_learn",
                serialization_format="cloudpickle",
                registered_model_name=reg_model_name,
            )
            
            model_uri = f"models:/{reg_model_name}/1"
            loaded_model = mlflow.sklearn.load_model(model_uri)
            print("--")
            """
            predictions = best_model.predict(X_test);
            r2_sq = round(r2_score(y_test, predictions),2)
            
            # Log parameters
            with mlflow.start_run(run_name = best_model_name):
                
                mlflow.set_tag("Model", best_model_name)
                # Set the active experiment
                #mlflow.set_experiment("App")

                # Create an MlflowClient object
                client = MlflowClient()
                runs = client.search_runs(
                        experiment_ids='0',
                        filter_string="metrics.r2 >0.7",
                        run_view_type=ViewType.ACTIVE_ONLY,
                        max_results=5,
                        order_by=["metrics.r2 DESC"]
                    )
                
                highest_r2 = -float('inf')
                run_ids_with_highest_r2 = []

                # Loop through the runs and find the highest r2 score
                for run in runs:
                    r2_scores = run.data.metrics['r2']
                    if r2_scores > highest_r2:
                        highest_r2 = r2_scores
                        run_ids_with_highest_r2 = [run.info.run_id]
                    elif r2_scores == highest_r2:
                        run_ids_with_highest_r2.append(run.info.run_id)

                # Register all models with the highest r2 score
                for run_id in run_ids_with_highest_r2:
                    model_uri = f"runs:/{run_id}/model"
                    mlflow.register_model(model_uri=model_uri, name="Default")
                
                """
                mlflow.sklearn.log_model(
                    sk_model=model,
                    artifact_path="sklearn-model",
                    registered_model_name=best_model_name,
    )
                wrappedModel = SklearnModelWrapper(best_model)
                conda_env = _mlflow_conda_env(
                    additional_conda_deps=None,
                    additional_pip_deps=["cloudpickle=={}".format(cloudpickle.__version__), "scikit-learn=={}".format(sklearn.__version__)],
                    additional_conda_channels=None,
                )
                
                
                mlflow.pyfunc.log_model(best_model_name,
                            python_model=wrappedModel,
                            conda_env=conda_env
                            )
                MLFLOW_TRACKING_URI = "sqlite:///mlflow.db"
                client = MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)

                print("h1")
                print(mlflow.list_experiments())
                print('h2')
                """
                # Evaluate best model
                predicted = best_model.predict(X_test)
                r2_square = round(r2_score(y_test, predicted), 2)
                rmse = round(np.sqrt(mean_squared_error(y_test, predicted)), 2)
                mae = round(mean_absolute_error(y_test, predicted), 2)

                # Log metrics
                mlflow.log_metric("r2", r2_square)
                mlflow.log_metric("rmse", rmse)
                mlflow.log_metric("mae", mae)
                mlflow.end_run()


            """
            ##Model Registration in MLflow Model Registry
            run_id = mlflow.search_runs(filter_string=f'tags.mlflow.runName ="{best_model_name}"').iloc[0].run_id
            model_name = best_model_name
            model_version = mlflow.register_model(f"runs:/{run_id}/MLmodel", best_model_name)
            # Registering the model takes a few seconds, so add a small delay
            time.sleep(15)

            client = MlflowClient()
            client.transition_model_version_stage(
            name=model_name,
            version=model_version.version,
            stage="Production",
            )           
            
            model = mlflow.pyfunc.load_model(f"runs:/{run_id}/MLmodel")

            
            # Sanity-check: This should match the AUC logged by MLflow
            print(f'R2: {r2_score(y_test, model.predict(X_test))}')
            """
            
            original_columns = set(feature.split('_', 1)[0] for feature in X_train)
            
            X_orig_selected = X_orig[list(original_columns)]
            
            #r2_square = round(r2_score(y_test, predicted), 2)
            
            ## Hyperparameter Tuning with MLflow
            """
            with mlflow.start_run():
                mlflow.set_tag("Model", best_model)
                
                if best_model_name == 'ElasticNet':
                    search_space = {'alpha': hp.loguniform('alpha', 0.01, 1),
                                    'l1_ratio': hp.loguniform('l1_ratio', 0, 1)}
                    
                    mlflow.set_tag("model", 'ElasticNet')
                    for alpha in search_space['alpha']:
                        for l1_ratio in search_space['l1_ratio']:
                            ml_model = ElasticNet(alpha=alpha, l1_ratio=l1_ratio).fit(X_train, y_train)
                            pred = ml_model.predict(X_test)
                            r2_sq = r2_score(pred, y_test)
                            
                            print("alpha:", alpha, "l1_ratio:", l1_ratio, "R2 Score:", r2_sq)
                            
                    mlflow.log_params({'n_estimators': n_estimators, 'max_depth': max_depth})
                    mlflow.log_metric("r2", r2_square)

                
                elif best_model_name == 'DecisionTreeRegressor':
                    search_space = {'min_samples_split': hp.loguniform('min_samples_split', 2, 10),
                                    'min_samples_leaf': hp.loguniform('min_samples_leaf', 1, 4)}
                    
                    mlflow.set_tag("model", 'DecisionTreeRegressor')
                    for min_samples_split in search_space['min_samples_split']:
                        for min_samples_leaf in search_space['min_samples_leaf']:
                            ml_model = DecisionTreeRegressor(min_samples_split=min_samples_split, min_samples_leaf=min_samples_leaf).fit(X_train, y_train)
                            pred = ml_model.predict(X_test)
                            r2_sq = r2_score(pred, y_test)
                            
                            print("min_samples_split:", min_samples_split, "min_samples_leaf:", min_samples_leaf, "R2 Score:", r2_sq)
                            
                    mlflow.log_params({'n_estimators': n_estimators, 'max_depth': max_depth})
                    mlflow.log_metric("r2", r2_square)

                elif best_model_name == 'RandomForestRegressor':
                    search_space = {'n_estimators': hp.loguniform('n_estimators', 10, 200),
                                    'max_depth': hp.loguniform('max_depth', 10, 50)}
                    
                    mlflow.set_tag("model", 'RandomForestRegressor')
                    for n_estimators in search_space['n_estimators']:
                        for max_depth in search_space['max_depth']:
                            ml_model = RandomForestRegressor(n_estimators=n_estimators, max_depth=max_depth).fit(X_train, y_train)
                            pred = ml_model.predict(X_test)
                            r2_sq = r2_score(pred, y_test)
                            
                            print("n_estimators:", n_estimators, "Max Depth:", max_depth, "R2 Score:", r2_sq)
                            
                    mlflow.log_params({'n_estimators': n_estimators, 'max_depth': max_depth})
                    mlflow.log_metric("r2", r2_square)

                elif best_model_name == 'GradientBoostingRegressor':
                    search_space = {'learning_rate': [0.001, 0.01, 0.1],
                                    'max_depth': [3, 4, 5, 6]}
                    
                    mlflow.set_tag("model", 'GradientBoostingRegressor')
                    for learning_rate in search_space['learning_rate']:
                        for max_depth in search_space['max_depth']:
                            ml_model = GradientBoostingRegressor(learning_rate=learning_rate, max_depth=max_depth).fit(X_train, y_train)
                            pred = ml_model.predict(X_test)
                            r2_sq = r2_score(pred, y_test)
                            
                            print("Learning Rate:", learning_rate, "Max Depth:", max_depth, "R2 Score:", r2_sq)
                            
                    mlflow.log_params({'learning_rate': learning_rate, 'max_depth': max_depth})
                    mlflow.log_metric("r2", r2_square)
                """

            return r2_sq
        
        except Exception as e:
            raise CustomException(e, sys)
        
            
