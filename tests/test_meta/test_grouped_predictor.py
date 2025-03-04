import pytest
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.dummy import DummyRegressor

from sklego.common import flatten
from sklego.meta import GroupedPredictor
from sklego.datasets import load_chicken

from tests.conftest import general_checks, select_tests


@pytest.mark.parametrize(
    "test_fn",
    select_tests(
        flatten([general_checks]),
        exclude=[
            # Nonsense checks because we always need at least two columns (group and value)
            "check_fit1d",
            "check_fit2d_predict1d",
            "check_fit2d_1feature",
            "check_transformer_data_not_an_array",
        ],
    ),
)
def test_estimator_checks(test_fn):
    clf = GroupedPredictor(
        estimator=LinearRegression(), groups=0, use_global_model=True
    )
    test_fn(GroupedPredictor.__name__ + "_fallback", clf)

    clf = GroupedPredictor(
        estimator=LinearRegression(), groups=0, use_global_model=False
    )
    test_fn(GroupedPredictor.__name__ + "_nofallback", clf)


def test_chickweight_df1_keys():
    df = load_chicken(as_frame=True)
    mod = GroupedPredictor(estimator=LinearRegression(), groups="diet")
    mod.fit(df[["time", "diet"]], df["weight"])
    assert set(mod.estimators_.keys()) == {1, 2, 3, 4}


def test_chickweight_df2_keys():
    df = load_chicken(as_frame=True)
    mod = GroupedPredictor(estimator=LinearRegression(), groups="chick")
    mod.fit(df[["time", "chick"]], df["weight"])
    assert set(mod.estimators_.keys()) == set(range(1, 50 + 1))


def test_chickweight_can_do_fallback():
    df = load_chicken(as_frame=True)
    mod = GroupedPredictor(estimator=LinearRegression(), groups="diet")
    mod.fit(df[["time", "diet"]], df["weight"])
    assert set(mod.estimators_.keys()) == {1, 2, 3, 4}
    to_predict = pd.DataFrame({"time": [21, 21], "diet": [5, 6]})
    assert mod.predict(to_predict).shape == (2,)
    assert mod.predict(to_predict)[0] == mod.predict(to_predict)[1]


def test_fallback_can_raise_error():
    df = load_chicken(as_frame=True)
    mod = GroupedPredictor(
        estimator=LinearRegression(),
        groups="diet",
        use_global_model=False,
        shrinkage=None,
    )
    mod.fit(df[["time", "diet"]], df["weight"])
    to_predict = pd.DataFrame({"time": [21, 21], "diet": [5, 6]})
    with pytest.raises(ValueError) as e:
        mod.predict(to_predict)
        assert "found a group" in str(e)


def test_chickweight_raise_error_group_col_missing():
    df = load_chicken(as_frame=True)
    mod = GroupedPredictor(estimator=LinearRegression(), groups="diet")
    mod.fit(df[["time", "diet"]], df["weight"])
    with pytest.raises(ValueError) as e:
        mod.predict(df[["time", "chick"]])
        assert "not in columns" in str(e)


def test_chickweight_raise_error_value_col_missing():
    df = load_chicken(as_frame=True)
    mod = GroupedPredictor(estimator=LinearRegression(), groups="diet")
    mod.fit(df[["time", "diet"]], df["weight"])

    with pytest.raises(ValueError):
        # Former test not valid anymore because we don't check for value columns
        # mod.predict(df[["diet", "chick"]])
        mod.predict(df[["diet"]])


def test_chickweight_np_keys():
    df = load_chicken(as_frame=True)
    mod = GroupedPredictor(estimator=LinearRegression(), groups=[1, 2])
    mod.fit(df[["time", "chick", "diet"]].values, df["weight"].values)
    # there should still only be 50 groups on this dataset
    assert len(mod.estimators_.keys()) == 50


def test_chickweigt_string_groups():

    df = load_chicken(as_frame=True)
    df["diet"] = ["omgomgomg" + s for s in df["diet"].astype(str)]

    X = df[["time", "diet"]]
    X_np = np.array(X)

    y = df["weight"]

    # This should NOT raise errors
    GroupedPredictor(LinearRegression(), groups=["diet"]).fit(X, y).predict(X)
    GroupedPredictor(LinearRegression(), groups=1).fit(X_np, y).predict(X_np)


@pytest.fixture
def shrinkage_data():
    df = pd.DataFrame(
        {
            "Planet": ["Earth", "Earth", "Earth", "Earth"],
            "Country": ["NL", "NL", "BE", "BE"],
            "City": ["Amsterdam", "Rotterdam", "Antwerp", "Brussels"],
            "Target": [1, 3, 2, 4],
        }
    )

    means = {
        "Earth": 2.5,
        "NL": 2,
        "BE": 3,
        "Amsterdam": 1,
        "Rotterdam": 3,
        "Antwerp": 2,
        "Brussels": 4,
    }

    return df, means


def test_constant_shrinkage(shrinkage_data):
    df, means = shrinkage_data

    X, y = df.drop(columns="Target"), df["Target"]

    shrink_est = GroupedPredictor(
        DummyRegressor(),
        ["Planet", "Country", "City"],
        shrinkage="constant",
        use_global_model=False,
        alpha=0.1,
    )

    shrinkage_factors = np.array([0.01, 0.09, 0.9])

    shrink_est.fit(X, y)

    expected_prediction = [
        np.array([means["Earth"], means["NL"], means["Amsterdam"]]) @ shrinkage_factors,
        np.array([means["Earth"], means["NL"], means["Rotterdam"]]) @ shrinkage_factors,
        np.array([means["Earth"], means["BE"], means["Antwerp"]]) @ shrinkage_factors,
        np.array([means["Earth"], means["BE"], means["Brussels"]]) @ shrinkage_factors,
    ]

    for exp, pred in zip(expected_prediction, shrink_est.predict(X).tolist()):
        assert pytest.approx(exp) == pred


def test_relative_shrinkage(shrinkage_data):
    df, means = shrinkage_data

    X, y = df.drop(columns="Target"), df["Target"]

    shrink_est = GroupedPredictor(
        DummyRegressor(),
        ["Planet", "Country", "City"],
        shrinkage="relative",
        use_global_model=False,
    )

    shrinkage_factors = np.array([4, 2, 1]) / 7

    shrink_est.fit(X, y)

    expected_prediction = [
        np.array([means["Earth"], means["NL"], means["Amsterdam"]]) @ shrinkage_factors,
        np.array([means["Earth"], means["NL"], means["Rotterdam"]]) @ shrinkage_factors,
        np.array([means["Earth"], means["BE"], means["Antwerp"]]) @ shrinkage_factors,
        np.array([means["Earth"], means["BE"], means["Brussels"]]) @ shrinkage_factors,
    ]

    for exp, pred in zip(expected_prediction, shrink_est.predict(X).tolist()):
        assert pytest.approx(exp) == pred


def test_min_n_obs_shrinkage(shrinkage_data):
    df, means = shrinkage_data

    X, y = df.drop(columns="Target"), df["Target"]

    shrink_est = GroupedPredictor(
        DummyRegressor(),
        ["Planet", "Country", "City"],
        shrinkage="min_n_obs",
        use_global_model=False,
        min_n_obs=2,
    )

    shrink_est.fit(X, y)

    expected_prediction = [means["NL"], means["NL"], means["BE"], means["BE"]]

    for exp, pred in zip(expected_prediction, shrink_est.predict(X).tolist()):
        assert pytest.approx(exp) == pred


def test_min_n_obs_shrinkage_too_little_obs(shrinkage_data):
    df, means = shrinkage_data

    X, y = df.drop(columns="Target"), df["Target"]

    too_big_n_obs = X.shape[0] + 1

    shrink_est = GroupedPredictor(
        DummyRegressor(),
        ["Planet", "Country", "City"],
        shrinkage="min_n_obs",
        use_global_model=False,
        min_n_obs=too_big_n_obs,
    )

    with pytest.raises(ValueError) as e:
        shrink_est.fit(X, y)

        assert (
            f"There is no group with size greater than or equal to {too_big_n_obs}"
            in str(e)
        )


def test_custom_shrinkage(shrinkage_data):
    df, means = shrinkage_data

    X, y = df.drop(columns="Target"), df["Target"]

    def shrinkage_func(group_sizes):
        n = len(group_sizes)
        return np.repeat(1 / n, n)

    shrink_est = GroupedPredictor(
        DummyRegressor(),
        ["Planet", "Country", "City"],
        shrinkage=shrinkage_func,
        use_global_model=False,
    )

    shrinkage_factors = np.array([1, 1, 1]) / 3

    shrink_est.fit(X, y)

    expected_prediction = [
        np.array([means["Earth"], means["NL"], means["Amsterdam"]]) @ shrinkage_factors,
        np.array([means["Earth"], means["NL"], means["Rotterdam"]]) @ shrinkage_factors,
        np.array([means["Earth"], means["BE"], means["Antwerp"]]) @ shrinkage_factors,
        np.array([means["Earth"], means["BE"], means["Brussels"]]) @ shrinkage_factors,
    ]

    assert expected_prediction == shrink_est.predict(X).tolist()


def test_custom_shrinkage_wrong_return_type(shrinkage_data):
    df, means = shrinkage_data

    X, y = df.drop(columns="Target"), df["Target"]

    def shrinkage_func(group_sizes):
        return group_sizes

    with pytest.raises(ValueError) as e:
        shrink_est = GroupedPredictor(
            DummyRegressor(),
            ["Planet", "Country", "City"],
            shrinkage=shrinkage_func,
            use_global_model=False,
        )

        shrink_est.fit(X, y)

        assert "should return an np.ndarray" in str(e)


def test_custom_shrinkage_wrong_length(shrinkage_data):
    df, means = shrinkage_data

    X, y = df.drop(columns="Target"), df["Target"]

    def shrinkage_func(group_sizes):
        n = len(group_sizes)
        return np.repeat(1 / n, n + 1)

    with pytest.raises(ValueError) as e:
        shrink_est = GroupedPredictor(
            DummyRegressor(),
            ["Planet", "Country", "City"],
            shrinkage=shrinkage_func,
            use_global_model=False,
        )

        shrink_est.fit(X, y)

        assert ".shape should be " in str(e)


def test_custom_shrinkage_raises_error(shrinkage_data):
    df, means = shrinkage_data

    X, y = df.drop(columns="Target"), df["Target"]

    def shrinkage_func(group_sizes):
        raise KeyError("This function is bad and you should feel bad")

    with pytest.raises(ValueError) as e:
        shrink_est = GroupedPredictor(
            DummyRegressor(),
            ["Planet", "Country", "City"],
            shrinkage=shrinkage_func,
            use_global_model=False,
        )

        shrink_est.fit(X, y)

        assert "you should feel bad" in str(
            e
        ) and "while checking the shrinkage function" in str(e)


@pytest.mark.parametrize("wrong_func", [list(), tuple(), dict(), 9])
def test_invalid_shrinkage(shrinkage_data, wrong_func):
    df, means = shrinkage_data

    X, y = df.drop(columns="Target"), df["Target"]

    with pytest.raises(ValueError) as e:
        shrink_est = GroupedPredictor(
            DummyRegressor(),
            ["Planet", "Country", "City"],
            shrinkage=wrong_func,
            use_global_model=False,
        )

        shrink_est.fit(X, y)

        assert "Invalid shrinkage specified." in str(e)


def test_global_model_shrinkage(shrinkage_data):
    df, means = shrinkage_data

    X, y = df.drop(columns="Target"), df["Target"]

    shrink_est_without_global = GroupedPredictor(
        DummyRegressor(),
        ["Planet", "Country", "City"],
        shrinkage="min_n_obs",
        use_global_model=False,
        min_n_obs=2,
    )

    shrink_est_with_global = GroupedPredictor(
        DummyRegressor(),
        ["Country", "City"],
        shrinkage="min_n_obs",
        use_global_model=True,
        min_n_obs=2,
    )

    shrink_est_without_global.fit(X, y)
    # Drop planet because otherwise it is seen as a value column
    shrink_est_with_global.fit(X.drop(columns="Planet"), y)

    pd.testing.assert_series_equal(
        shrink_est_with_global.predict(X.drop(columns="Planet")),
        shrink_est_without_global.predict(X),
    )


def test_shrinkage_single_group(shrinkage_data):
    df, means = shrinkage_data

    X, y = df.drop(columns="Target"), df["Target"]

    shrink_est = GroupedPredictor(
        DummyRegressor(),
        "Country",
        shrinkage="constant",
        use_global_model=True,
        alpha=0.1,
    )

    shrinkage_factors = np.array([0.1, 0.9])

    # Drop planet and city because otherwise they are seen as value columns
    shrink_est.fit(X[["Country"]], y)

    expected_prediction = [
        np.array([means["Earth"], means["NL"]]) @ shrinkage_factors,
        np.array([means["Earth"], means["NL"]]) @ shrinkage_factors,
        np.array([means["Earth"], means["BE"]]) @ shrinkage_factors,
        np.array([means["Earth"], means["BE"]]) @ shrinkage_factors,
    ]

    assert expected_prediction == shrink_est.predict(X[["Country"]]).tolist()


def test_shrinkage_single_group_no_global(shrinkage_data):
    df, means = shrinkage_data

    X, y = df.drop(columns="Target"), df["Target"]

    with pytest.raises(ValueError) as e:
        shrink_est = GroupedPredictor(
            DummyRegressor(),
            "Country",
            shrinkage="constant",
            use_global_model=False,
            alpha=0.1,
        )
        shrink_est.fit(X, y)

        assert (
            "Cannot do shrinkage with a single group if use_global_model is False"
            in str(e)
        )


def test_unexisting_shrinkage_func(shrinkage_data):
    df, means = shrinkage_data

    X, y = df.drop(columns="Target"), df["Target"]

    with pytest.raises(ValueError) as e:
        unexisting_func = "some_highly_unlikely_function_name"

        shrink_est = GroupedPredictor(
            estimator=DummyRegressor(),
            groups=["Planet", "Country"],
            shrinkage=unexisting_func,
        )

        shrink_est.fit(X, y)

        assert "shrinkage function" in str(e)


def test_unseen_groups_shrinkage(shrinkage_data):
    df, means = shrinkage_data

    X, y = df.drop(columns="Target"), df["Target"]

    shrink_est = GroupedPredictor(
        DummyRegressor(), ["Planet", "Country", "City"], shrinkage="constant", alpha=0.1
    )

    shrink_est.fit(X, y)

    unseen_group = pd.DataFrame(
        {"Planet": ["Earth"], "Country": ["DE"], "City": ["Hamburg"]}
    )

    with pytest.raises(ValueError) as e:
        shrink_est.predict(X=pd.concat([unseen_group] * 4, axis=0))
        assert "found a group" in str(e)


def test_predict_missing_group_column(shrinkage_data):
    df, means = shrinkage_data

    X, y = df.drop(columns="Target"), df["Target"]

    shrink_est = GroupedPredictor(
        DummyRegressor(),
        ["Planet", "Country", "City"],
        shrinkage="constant",
        use_global_model=False,
        alpha=0.1,
    )

    shrink_est.fit(X, y)

    with pytest.raises(ValueError) as e:
        shrink_est.predict(X.drop(columns=["Country"]))
        assert "group columns" in str(e)


def test_predict_missing_value_column(shrinkage_data):
    df, means = shrinkage_data

    value_column = "predictor"

    X, y = df.drop(columns="Target"), df["Target"]
    X = X.assign(**{value_column: np.random.normal(size=X.shape[0])})

    shrink_est = GroupedPredictor(
        LinearRegression(),
        ["Planet", "Country", "City"],
        shrinkage="constant",
        use_global_model=False,
        alpha=0.1,
    )

    shrink_est.fit(X, y)

    with pytest.raises(ValueError) as e:
        shrink_est.predict(X.drop(columns=[value_column]))
        assert "columns to use" in str(e)


def test_bad_shrinkage_value_error():
    with pytest.raises(ValueError) as e:
        df = load_chicken(as_frame=True)
        mod = GroupedPredictor(
            estimator=LinearRegression(), groups="diet", shrinkage="dinosaurhead"
        )
        mod.fit(df[["time", "diet"]], df["weight"])
        assert "shrinkage function" in str(e)
