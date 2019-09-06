import pandas as pd

from evaluate.probe import ProbeHeader
from evaluate.calculator import RecallCalculator, StatisticalClassification
from evaluate.classification import AlignmentAssessment

import pytest


def create_report_row(
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


class TestRecallCalculator:
    def test_init_gtconfIsExtractedCorrectly(self):
        columns = ["sample", "query_probe_header", "ref_probe_header", "classification"]
        report = pd.DataFrame(
            data=[
                create_report_row(AlignmentAssessment.UNMAPPED, gt_conf=100),
                create_report_row(AlignmentAssessment.UNMAPPED, gt_conf=100),
                create_report_row(AlignmentAssessment.PRIMARY_CORRECT, gt_conf=10),
                create_report_row(AlignmentAssessment.PRIMARY_INCORRECT, gt_conf=100),
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

    def test_calculateRecall_noReportsReturnsZero(self):
        columns = ["sample", "query_probe_header", "ref_probe_header", "classification"]
        report = pd.DataFrame(columns=columns)
        calculator = RecallCalculator([report])
        threshold = 0

        actual = calculator.calculate_recall(conf_threshold=threshold)
        expected = 0

        assert actual == expected

    def test_calculateRecall_oneReportNoTruePositivesReturnsZero(self):
        columns = ["sample", "query_probe_header", "ref_probe_header", "classification"]
        report = pd.DataFrame(
            data=[
                create_report_row(AlignmentAssessment.UNMAPPED, gt_conf=100),
                create_report_row(AlignmentAssessment.UNMAPPED, gt_conf=100),
                create_report_row(AlignmentAssessment.PRIMARY_CORRECT, gt_conf=10),
                create_report_row(AlignmentAssessment.PRIMARY_INCORRECT, gt_conf=100),
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
                create_report_row(AlignmentAssessment.PRIMARY_CORRECT, gt_conf=100),
                create_report_row(AlignmentAssessment.PRIMARY_CORRECT, gt_conf=100),
                create_report_row(AlignmentAssessment.PRIMARY_INCORRECT, gt_conf=100),
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
                create_report_row(AlignmentAssessment.PRIMARY_CORRECT, gt_conf=10),
                create_report_row(AlignmentAssessment.PRIMARY_CORRECT, gt_conf=100),
                create_report_row(AlignmentAssessment.PRIMARY_CORRECT, gt_conf=100),
                create_report_row(AlignmentAssessment.UNMAPPED, gt_conf=100),
                create_report_row(
                    AlignmentAssessment.SUPPLEMENTARY_INCORRECT, gt_conf=10
                ),
                create_report_row(AlignmentAssessment.SECONDARY_CORRECT, gt_conf=100),
                create_report_row(AlignmentAssessment.PRIMARY_INCORRECT, gt_conf=100),
            ],
            columns=columns,
        )
        calculator = RecallCalculator([report])
        threshold = 60

        actual = calculator.calculate_recall(conf_threshold=threshold)
        expected = 0.5

        assert actual == expected

    def test_calculateRecall_oneReportNoTruePositivesOrFalseNegativesReturnsZero(self):
        columns = ["sample", "query_probe_header", "ref_probe_header", "classification"]
        report = pd.DataFrame(
            data=[
                create_report_row(
                    AlignmentAssessment.SUPPLEMENTARY_INCORRECT, gt_conf=100
                ),
                create_report_row(AlignmentAssessment.PRIMARY_INCORRECT, gt_conf=100),
            ],
            columns=columns,
        )
        calculator = RecallCalculator([report])
        threshold = 60

        actual = calculator.calculate_recall(conf_threshold=threshold)
        expected = 0

        assert actual == expected

    def test_calculateRecall_twoReportsHalfTruePositiveHalfFalseNegativeReturnsFifty(
        self
    ):
        columns = ["sample", "query_probe_header", "ref_probe_header", "classification"]
        report1 = pd.DataFrame(
            data=[
                create_report_row(AlignmentAssessment.PRIMARY_CORRECT, gt_conf=10),
                create_report_row(AlignmentAssessment.PRIMARY_CORRECT, gt_conf=100),
                create_report_row(AlignmentAssessment.PRIMARY_CORRECT, gt_conf=100),
                create_report_row(AlignmentAssessment.UNMAPPED, gt_conf=100),
                create_report_row(
                    AlignmentAssessment.SUPPLEMENTARY_INCORRECT, gt_conf=10
                ),
                create_report_row(AlignmentAssessment.SECONDARY_CORRECT, gt_conf=100),
                create_report_row(AlignmentAssessment.PRIMARY_INCORRECT, gt_conf=100),
            ],
            columns=columns,
        )
        report2 = pd.DataFrame(
            data=[
                create_report_row(AlignmentAssessment.PRIMARY_CORRECT, gt_conf=100),
                create_report_row(AlignmentAssessment.UNMAPPED, gt_conf=100),
                create_report_row(AlignmentAssessment.PRIMARY_INCORRECT, gt_conf=100),
            ],
            columns=columns,
        )
        calculator = RecallCalculator([report1, report2])
        threshold = 60

        actual = calculator.calculate_recall(conf_threshold=threshold)
        expected = 0.5

        assert actual == expected
