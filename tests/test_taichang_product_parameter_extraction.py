import unittest


class TaichangProductParameterExtractionTest(unittest.TestCase):
    def test_expands_rowspan_and_extracts_dimension_rows(self):
        from scripts.rag.extract_taichang_product_parameters import (
            _extract_html_tables,
            _metadata_from_tables,
            _parameter_rows_from_table,
        )

        markdown = """
        No:2024100312005501713
        <table>
          <tr><td>委托单位*</td><td colspan="3">河北泰昌电力器材科技有限公司</td></tr>
          <tr><td>样品名称*</td><td colspan="3">CPVC电缆保护管</td></tr>
          <tr><td>生产单位*</td><td colspan="3">河北泰昌电力器材科技有限公司</td></tr>
          <tr><td>规格型号*</td><td>DS 250×15×6000 SN16 PVC-C</td><td>样品等级*</td><td>合格品</td></tr>
          <tr><td>检验依据</td><td colspan="3">DL/T 802.1-2023</td></tr>
          <tr><td>检验结论</td><td colspan="3">符合DL/T 802.3-2023标准要求,该样品合格。</td></tr>
        </table>
        <table>
          <tr><td>序号</td><td colspan="2">检验项目</td><td>单位</td><td>标准要求</td><td>检验结果</td><td>单项结论</td></tr>
          <tr><td rowspan="2">3</td><td rowspan="2">尺寸</td><td>平均内径</td><td>mm</td><td>250.0~251.5</td><td>250.2~250.4</td><td>合格</td></tr>
          <tr><td>壁厚</td><td>mm</td><td>$15_{0}^{+1.8}$</td><td>15.2~15.3</td><td>合格</td></tr>
          <tr><td>4</td><td colspan="2">环刚度(80°C)</td><td>kN/m2</td><td>≥16</td><td>21.63</td><td>合格</td></tr>
        </table>
        """
        tables = _extract_html_tables(markdown)
        metadata = _metadata_from_tables(tables, markdown)
        rows = _parameter_rows_from_table(tables[1])

        self.assertEqual(metadata["report_no"], "2024100312005501713")
        self.assertEqual(metadata["product_family"], "CPVC电缆保护管")
        self.assertEqual(metadata["nominal_inner_diameter"], "250")
        self.assertTrue(any(row["parameter_name"] == "尺寸-平均内径" for row in rows))
        self.assertTrue(any(row["parameter_name"] == "尺寸-壁厚" and row["standard_requirement"] == "15_0^+1.8" for row in rows))
        self.assertTrue(any(row["parameter_name"] == "环刚度(80°C)" and row["inspection_result"] == "21.63" for row in rows))

    def test_builds_enterprise_fact_rows_without_coverage_judgement(self):
        from scripts.rag.extract_taichang_product_parameters import _build_qa_reference

        rows = [
            {"product_family": "MPP电缆保护管", "parameter_name": "尺寸-平均内径"},
            {"product_family": "MPP电缆保护管", "parameter_name": "环刚度"},
        ]
        qa = _build_qa_reference(rows, None)

        self.assertEqual(qa["scope"], "qa_only_not_coverage_judgement")
        self.assertIn("by_product_family", qa)


if __name__ == "__main__":
    unittest.main()
