import pandas as pd
import tempfile
from evaluate.probe import ProbeHeader
from evaluate.calculator import (
    RecallCalculator,
    StatisticalClassification,
    PrecisionCalculator,
    Calculator,
)
from evaluate.classification import AlignmentAssessment
from pathlib import Path

import pytest
from io import StringIO
import math


def create_tmp_file(contents: str) -> Path:
    with tempfile.NamedTemporaryFile(mode="r+", delete=False) as tmp:
        tmp.write(contents)
        tmp.truncate()

    return Path(tmp.name)


def create_recall_report_row(
    classification: AlignmentAssessment, gt_conf: float = 0, sample: str = "sample1"
) -> pd.Series:
    truth_probe_header = ProbeHeader()
    vcf_probe_header = ProbeHeader(gt_conf=gt_conf)
    data = {
        "sample": sample,
        "query_probe_header": str(truth_probe_header),
        "ref_probe_header": str(vcf_probe_header),
        "classification": classification,
    }
    return pd.Series(data=data)


def create_precision_report_row(
    classification: float, gt_conf: float = 0, sample: str = "sample1"
) -> pd.Series:
    ref_probe_header = ProbeHeader()
    pandora_probe_header = ProbeHeader(gt_conf=gt_conf)
    data = {
        "sample": sample,
        "query_probe_header": str(pandora_probe_header),
        "ref_probe_header": str(ref_probe_header),
        "classification": classification,
    }
    return pd.Series(data=data)


class TestCalculator:
    def test_getMaximumGtConf_no_gt_conf_columnRaisesKeyError(self):
        calculator = Calculator([pd.DataFrame()])
        with pytest.raises(KeyError):
            calculator.get_maximum_gt_conf()

    def test_getMaximumGtConf_emptyReportReturnsNaN(self):
        calculator = Calculator([pd.DataFrame(data={"gt_conf": []})])
        actual = calculator.get_maximum_gt_conf()

        assert math.isnan(actual)

    def test_getMaximumGtConf_oneGTConfInReportReturnsGTConf(self):
        calculator = Calculator([pd.DataFrame(data={"gt_conf": [1.5]})])
        actual = calculator.get_maximum_gt_conf()
        expected = 1.5

        assert actual == expected

    def test_getMaximumGtConf_threeGTConfsInReportReturnsHighest(self):
        calculator = Calculator([pd.DataFrame(data={"gt_conf": [1.5, 10.5, 5.0]})])
        actual = calculator.get_maximum_gt_conf()
        expected = 10.5

        assert actual == expected


class TestRecallCalculator:
    def test_fromFiles_TwoFilesReturnsValidRecallCalculator(self):
        contents_1 = """sample	query_probe_header	ref_probe_header	classification
CFT073	>CHROM=1;POS=1246;INTERVAL=[20,30);		unmapped
CFT073	>CHROM=1;POS=1248;INTERVAL=[30,40);	>CHROM=GC00005358_3;SAMPLE=CFT073;POS=1;INTERVAL=[0,17);SVTYPE=PH_SNPs;MEAN_FWD_COVG=3;MEAN_REV_COVG=6;GT_CONF=60.1133;	primary_correct
CFT073	>CHROM=1;POS=1252;INTERVAL=[40,50);		unmapped
"""
        contents_2 = """sample	query_probe_header	ref_probe_header	classification
CFT073	>CHROM=1;POS=1260;INTERVAL=[50,60);	>CHROM=GC00000578_3;SAMPLE=CFT073;POS=165;INTERVAL=[25,29);SVTYPE=PH_SNPs;MEAN_FWD_COVG=3;MEAN_REV_COVG=3;GT_CONF=3.22199;	primary_incorrect
CFT073	>CHROM=1;POS=1262;INTERVAL=[60,70);		unmapped
CFT073	>CHROM=1;POS=1281;INTERVAL=[70,80);		unmapped
"""
        path_1 = create_tmp_file(contents_1)
        path_2 = create_tmp_file(contents_2)

        contents_1_input = StringIO(contents_1)
        contents_2_input = StringIO(contents_2)
        dataframes = [
            pd.read_csv(contents_1_input, sep="\t", keep_default_na=False),
            pd.read_csv(contents_2_input, sep="\t", keep_default_na=False),
        ]

        actual = RecallCalculator.from_files([path_1, path_2])
        expected = RecallCalculator(dataframes)

        path_1.unlink()
        path_2.unlink()

        assert actual == expected

    def test_init_gtconfIsExtractedCorrectly(self):
        columns = ["sample", "query_probe_header", "ref_probe_header", "classification"]
        report = pd.DataFrame(
            data=[
                create_recall_report_row(AlignmentAssessment.UNMAPPED, gt_conf=100),
                create_recall_report_row(AlignmentAssessment.UNMAPPED, gt_conf=100),
                create_recall_report_row(
                    AlignmentAssessment.PRIMARY_CORRECT, gt_conf=10
                ),
                create_recall_report_row(
                    AlignmentAssessment.PRIMARY_INCORRECT, gt_conf=100
                ),
            ],
            columns=columns,
        )
        calculator = RecallCalculator([report])
        actual = calculator.report.gt_conf

        expected = pd.Series([100.0, 100.0, 10.0, 100.0])

        assert actual.equals(expected)

    def test_statisticalClassification_unmappedReturnsFalseNegative(self):
        classification = "unmapped"

        actual = RecallCalculator.statistical_classification(classification)
        expected = StatisticalClassification.FALSE_NEGATIVE

        assert actual == expected

    def test_statisticalClassification_partiallyMappedReturnsFalseNegative(self):
        classification = "partially_mapped"

        actual = RecallCalculator.statistical_classification(classification)
        expected = StatisticalClassification.FALSE_NEGATIVE

        assert actual == expected

    def test_statisticalClassification_incorrectReturnsFalsePositive(self):
        classification = AlignmentAssessment.PRIMARY_INCORRECT.value

        actual = RecallCalculator.statistical_classification(classification)
        expected = StatisticalClassification.FALSE_POSITIVE

        assert actual == expected

    def test_statisticalClassification_correctReturnsTruePositive(self):
        classification = AlignmentAssessment.PRIMARY_CORRECT.value
        actual = RecallCalculator.statistical_classification(classification)
        expected = StatisticalClassification.TRUE_POSITIVE

        assert actual == expected

    def test_statisticalClassification_secondaryIncorrectReturnsFalsePositive(self):
        classification = AlignmentAssessment.SECONDARY_INCORRECT.value

        actual = RecallCalculator.statistical_classification(classification)
        expected = StatisticalClassification.FALSE_POSITIVE

        assert actual == expected

    def test_statisticalClassification_secondaryCorrectReturnsTruePositive(self):
        classification = AlignmentAssessment.SECONDARY_CORRECT.value

        actual = RecallCalculator.statistical_classification(classification)
        expected = StatisticalClassification.TRUE_POSITIVE

        assert actual == expected

    def test_statisticalClassification_supplementaryIncorrectReturnsFalsePositive(self):
        classification = AlignmentAssessment.SUPPLEMENTARY_INCORRECT.value

        actual = RecallCalculator.statistical_classification(classification)
        expected = StatisticalClassification.FALSE_POSITIVE

        assert actual == expected

    def test_statisticalClassification_supplementaryCorrectReturnsTruePositive(self):
        classification = AlignmentAssessment.SUPPLEMENTARY_CORRECT.value

        actual = RecallCalculator.statistical_classification(classification)
        expected = StatisticalClassification.TRUE_POSITIVE

        assert actual == expected

    def test_statisticalClassification_invalidClassificationRaisesValueError(self):
        classification = "invalid"

        with pytest.raises(ValueError):
            RecallCalculator.statistical_classification(classification)

    def test_calculateRecall_noReportsRaisesValueError(self):
        columns = ["sample", "query_probe_header", "ref_probe_header", "classification"]
        report = pd.DataFrame(columns=columns)
        calculator = RecallCalculator([report])
        threshold = 0

        with pytest.raises(ValueError):
            calculator.calculate_recall(conf_threshold=threshold)

    def test_calculateRecall_oneReportNoTruePositivesReturnsZero(self):
        columns = ["sample", "query_probe_header", "ref_probe_header", "classification"]
        report = pd.DataFrame(
            data=[
                create_recall_report_row(AlignmentAssessment.UNMAPPED, gt_conf=100),
                create_recall_report_row(AlignmentAssessment.UNMAPPED, gt_conf=100),
                create_recall_report_row(
                    AlignmentAssessment.PRIMARY_CORRECT, gt_conf=10
                ),
                create_recall_report_row(
                    AlignmentAssessment.PRIMARY_INCORRECT, gt_conf=100
                ),
            ],
            columns=columns,
        )
        calculator = RecallCalculator([report])
        threshold = 60

        actual = calculator.calculate_recall(conf_threshold=threshold)
        expected = 0

        assert actual == expected

    def test_calculateRecall_oneReportNoFalseNegativesReturnsOne(self):
        columns = ["sample", "query_probe_header", "ref_probe_header", "classification"]
        report = pd.DataFrame(
            data=[
                create_recall_report_row(
                    AlignmentAssessment.PRIMARY_CORRECT, gt_conf=100
                ),
                create_recall_report_row(
                    AlignmentAssessment.PRIMARY_CORRECT, gt_conf=100
                ),
                create_recall_report_row(
                    AlignmentAssessment.PRIMARY_INCORRECT, gt_conf=100
                ),
            ],
            columns=columns,
        )
        calculator = RecallCalculator([report])
        threshold = 60

        actual = calculator.calculate_recall(conf_threshold=threshold)
        expected = 1

        assert actual == expected

    def test_calculateRecall_oneReportHalfTruePositiveHalfFalseNegativeReturnsFifty(
        self
    ):
        columns = ["sample", "query_probe_header", "ref_probe_header", "classification"]
        report = pd.DataFrame(
            data=[
                create_recall_report_row(
                    AlignmentAssessment.PRIMARY_CORRECT, gt_conf=10
                ),
                create_recall_report_row(
                    AlignmentAssessment.PRIMARY_CORRECT, gt_conf=100
                ),
                create_recall_report_row(
                    AlignmentAssessment.PRIMARY_CORRECT, gt_conf=100
                ),
                create_recall_report_row(AlignmentAssessment.UNMAPPED, gt_conf=100),
                create_recall_report_row(
                    AlignmentAssessment.SUPPLEMENTARY_INCORRECT, gt_conf=10
                ),
                create_recall_report_row(
                    AlignmentAssessment.SECONDARY_CORRECT, gt_conf=100
                ),
                create_recall_report_row(
                    AlignmentAssessment.PRIMARY_INCORRECT, gt_conf=100
                ),
            ],
            columns=columns,
        )
        calculator = RecallCalculator([report])
        threshold = 60

        actual = calculator.calculate_recall(conf_threshold=threshold)
        expected = 0.5

        assert actual == expected

    def test_calculateRecall_oneReportNoTruePositivesOrFalseNegativesRaisesValueError(self):
        columns = ["sample", "query_probe_header", "ref_probe_header", "classification"]
        report = pd.DataFrame(
            data=[
                create_recall_report_row(
                    AlignmentAssessment.SUPPLEMENTARY_INCORRECT, gt_conf=100
                ),
                create_recall_report_row(
                    AlignmentAssessment.PRIMARY_INCORRECT, gt_conf=100
                ),
            ],
            columns=columns,
        )
        calculator = RecallCalculator([report])
        threshold = 60

        with pytest.raises(ValueError):
            calculator.calculate_recall(conf_threshold=threshold)

    def test_calculateRecall_oneReportAllTruePositivesAllBelowThresholdRaisesValueError(self):
        columns = ["sample", "query_probe_header", "ref_probe_header", "classification"]
        report = pd.DataFrame(
            data=[
                create_recall_report_row(
                    AlignmentAssessment.PRIMARY_CORRECT, gt_conf=50
                ),
                create_recall_report_row(
                    AlignmentAssessment.PRIMARY_CORRECT, gt_conf=80
                ),
            ],
            columns=columns,
        )
        calculator = RecallCalculator([report])
        threshold = 100

        actual = calculator.calculate_recall(conf_threshold=threshold)
        expected = 0.0

        assert actual == expected

    def test_calculateRecall_twoReportsHalfTruePositiveHalfFalseNegativeReturnsFifty(
        self
    ):
        columns = ["sample", "query_probe_header", "ref_probe_header", "classification"]
        report1 = pd.DataFrame(
            data=[
                create_recall_report_row(
                    AlignmentAssessment.PRIMARY_CORRECT, gt_conf=10
                ),
                create_recall_report_row(
                    AlignmentAssessment.PRIMARY_CORRECT, gt_conf=100
                ),
                create_recall_report_row(
                    AlignmentAssessment.PRIMARY_CORRECT, gt_conf=100
                ),
                create_recall_report_row(AlignmentAssessment.UNMAPPED, gt_conf=100),
                create_recall_report_row(
                    AlignmentAssessment.SUPPLEMENTARY_INCORRECT, gt_conf=10
                ),
                create_recall_report_row(
                    AlignmentAssessment.SECONDARY_CORRECT, gt_conf=100
                ),
                create_recall_report_row(
                    AlignmentAssessment.PRIMARY_INCORRECT, gt_conf=100
                ),
            ],
            columns=columns,
        )
        report2 = pd.DataFrame(
            data=[
                create_recall_report_row(
                    AlignmentAssessment.PRIMARY_CORRECT, gt_conf=100
                ),
                create_recall_report_row(AlignmentAssessment.UNMAPPED, gt_conf=100),
                create_recall_report_row(
                    AlignmentAssessment.PRIMARY_INCORRECT, gt_conf=100
                ),
            ],
            columns=columns,
        )
        calculator = RecallCalculator([report1, report2])
        threshold = 60

        actual = calculator.calculate_recall(conf_threshold=threshold)
        expected = 0.5

        assert actual == expected


class TestPrecisionCalculator:
    def test_init_gtconfIsExtractedCorrectly(self):
        columns = ["sample", "query_probe_header", "ref_probe_header", "classification"]
        report = pd.DataFrame(
            data=[
                create_precision_report_row(0.0, gt_conf=100),
                create_precision_report_row(0.0, gt_conf=100),
                create_precision_report_row(0.0, gt_conf=10),
                create_precision_report_row(0.0, gt_conf=100),
            ],
            columns=columns,
        )
        calculator = PrecisionCalculator([report])
        actual = calculator.report.gt_conf

        expected = pd.Series([100.0, 100.0, 10.0, 100.0])

        assert actual.equals(expected)

    def test_calculatePrecision_NoReportsRaisesValueError(self):
        columns = ["sample", "query_probe_header", "ref_probe_header", "classification"]
        report = pd.DataFrame(columns=columns)
        calculator = PrecisionCalculator([report])

        with pytest.raises(ValueError):
            calculator.calculate_precision()

    def test_calculatePrecision_OneReportWithOneRowCompletelyCorrectReturnsOne(self):
        columns = ["sample", "query_probe_header", "ref_probe_header", "classification"]
        report = pd.DataFrame(
            data=[create_precision_report_row(1.0, gt_conf=100)], columns=columns
        )
        calculator = PrecisionCalculator([report])

        actual = calculator.calculate_precision()
        expected = 1.0

        assert actual == expected

    def test_calculatePrecision_OneReportWithOneRowCompletelyIncorrectReturnsZero(self):
        columns = ["sample", "query_probe_header", "ref_probe_header", "classification"]
        report = pd.DataFrame(
            data=[create_precision_report_row(0.0, gt_conf=100)], columns=columns
        )
        calculator = PrecisionCalculator([report])

        actual = calculator.calculate_precision()
        expected = 0.0

        assert actual == expected

    def test_calculatePrecision_OneReportWithOneRowCompletelyCorrectBelowConfThreasholdRaisesValueError(
        self
    ):
        columns = ["sample", "query_probe_header", "ref_probe_header", "classification"]
        report = pd.DataFrame(
            data=[create_precision_report_row(1.0, gt_conf=10)], columns=columns
        )
        calculator = PrecisionCalculator([report])
        confidence_threshold = 60

        with pytest.raises(ValueError):
            calculator.calculate_precision(confidence_threshold)

    def test_calculatePrecision_OneReportWithOneRowCompletelyCorrectEqualConfThreasholdReturnsOne(
        self
    ):
        columns = ["sample", "query_probe_header", "ref_probe_header", "classification"]
        report = pd.DataFrame(
            data=[create_precision_report_row(1.0, gt_conf=60)], columns=columns
        )
        calculator = PrecisionCalculator([report])
        confidence_threshold = 60

        actual = calculator.calculate_precision(confidence_threshold)
        expected = 1.0

        assert actual == expected

    def test_calculatePrecision_OneReportWithTwoRowsPartiallyCorrect(self):
        columns = ["sample", "query_probe_header", "ref_probe_header", "classification"]
        report = pd.DataFrame(
            data=[
                create_precision_report_row(0.5, gt_conf=100),
                create_precision_report_row(0.7, gt_conf=100),
            ],
            columns=columns,
        )
        calculator = PrecisionCalculator([report])

        actual = calculator.calculate_precision()
        expected = 1.2 / 2

        assert actual == expected

    def test_calculatePrecision_OneReportWithThreeRowsTwoPartiallyCorrectOneBelowThreshold(
        self
    ):
        columns = ["sample", "query_probe_header", "ref_probe_header", "classification"]
        report = pd.DataFrame(
            data=[
                create_precision_report_row(0.4, gt_conf=100),
                create_precision_report_row(0.8, gt_conf=20),
                create_precision_report_row(0.3, gt_conf=100),
            ],
            columns=columns,
        )
        calculator = PrecisionCalculator([report])
        confidence_threshold = 80

        actual = calculator.calculate_precision(confidence_threshold)
        expected = 0.7 / 2

        assert actual == expected
