import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DynamicFormRenderer, type FormField } from '@/components/forms/DynamicFormRenderer';

// ─── 测试辅助 ──────────────────────────────────────────────

function renderForm(
  fields: FormField[],
  values: Record<string, any> = {},
  options: { readOnly?: boolean; onChange?: (key: string, val: any) => void } = {},
) {
  const onChange = options.onChange || vi.fn();
  return {
    onChange,
    ...render(
      <DynamicFormRenderer
        fields={fields}
        values={values}
        onChange={onChange}
        readOnly={options.readOnly}
      />,
    ),
  };
}

// ─── 测试用例 ──────────────────────────────────────────────

describe('DynamicFormRenderer', () => {
  describe('字段类型渲染', () => {
    it('渲染 text 字段', () => {
      const fields: FormField[] = [
        { key: 'name', label: '姓名', type: 'text', placeholder: '请输入姓名' },
      ];
      renderForm(fields);

      expect(screen.getByText('姓名')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('请输入姓名')).toBeInTheDocument();
    });

    it('渲染 number 字段', () => {
      const fields: FormField[] = [
        { key: 'amount', label: '金额', type: 'number', min: 0, max: 10000 },
      ];
      renderForm(fields);

      expect(screen.getByText('金额')).toBeInTheDocument();
      const input = screen.getByPlaceholderText('请输入金额') as HTMLInputElement;
      expect(input.type).toBe('number');
    });

    it('渲染 textarea 字段', () => {
      const fields: FormField[] = [
        { key: 'reason', label: '原因', type: 'textarea' },
      ];
      renderForm(fields);

      expect(screen.getByText('原因')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('请输入原因')).toBeInTheDocument();
    });

    it('渲染 date 字段', () => {
      const fields: FormField[] = [
        { key: 'start_date', label: '开始日期', type: 'date' },
      ];
      renderForm(fields);

      expect(screen.getByText('开始日期')).toBeInTheDocument();
    });

    it('渲染 select 字段及选项', () => {
      const fields: FormField[] = [
        { key: 'dept', label: '部门', type: 'select', options: ['技术部', '市场部', '人事部'] },
      ];
      renderForm(fields);

      expect(screen.getByText('部门')).toBeInTheDocument();
    });

    it('渲染 multiselect 字段', () => {
      const fields: FormField[] = [
        { key: 'skills', label: '技能', type: 'multiselect', options: ['React', 'Vue', 'Angular'] },
      ];
      renderForm(fields);

      expect(screen.getByText('技能')).toBeInTheDocument();
      expect(screen.getByText('React')).toBeInTheDocument();
      expect(screen.getByText('Vue')).toBeInTheDocument();
      expect(screen.getByText('Angular')).toBeInTheDocument();
    });

    it('渲染空字段列表时显示提示', () => {
      renderForm([]);
      expect(screen.getByText('暂无表单字段')).toBeInTheDocument();
    });
  });

  describe('readOnly 模式', () => {
    it('文本字段只读时显示值', () => {
      const fields: FormField[] = [
        { key: 'name', label: '姓名', type: 'text' },
      ];
      renderForm(fields, { name: '张三' }, { readOnly: true });

      expect(screen.getByText('张三')).toBeInTheDocument();
      // 不应显示输入框
      expect(screen.queryByRole('textbox')).toBeNull();
    });

    it('空值只读时显示"未填写"', () => {
      const fields: FormField[] = [
        { key: 'name', label: '姓名', type: 'text' },
      ];
      renderForm(fields, {}, { readOnly: true });

      expect(screen.getByText('未填写')).toBeInTheDocument();
    });

    it('数字字段只读时显示数字值', () => {
      const fields: FormField[] = [
        { key: 'amount', label: '金额', type: 'number' },
      ];
      renderForm(fields, { amount: 5000 }, { readOnly: true });

      expect(screen.getByText('5000')).toBeInTheDocument();
    });
  });

  describe('required 字段标记', () => {
    it('必填字段显示红色星号', () => {
      const fields: FormField[] = [
        { key: 'name', label: '姓名', type: 'text', required: true },
      ];
      renderForm(fields);

      expect(screen.getByText('*')).toBeInTheDocument();
    });

    it('非必填字段不显示星号', () => {
      const fields: FormField[] = [
        { key: 'name', label: '姓名', type: 'text', required: false },
      ];
      renderForm(fields);

      expect(screen.queryByText('*')).toBeNull();
    });
  });

  describe('onChange 回调', () => {
    it('text 字段输入触发 onChange', () => {
      const fields: FormField[] = [
        { key: 'name', label: '姓名', type: 'text' },
      ];
      const { onChange } = renderForm(fields);

      const input = screen.getByPlaceholderText('请输入姓名');
      fireEvent.change(input, { target: { value: '测试' } });

      expect(onChange).toHaveBeenCalledWith('name', '测试');
    });

    it('number 字段输入触发 onChange', () => {
      const fields: FormField[] = [
        { key: 'amount', label: '金额', type: 'number' },
      ];
      const { onChange } = renderForm(fields);

      const input = screen.getByPlaceholderText('请输入金额');
      fireEvent.change(input, { target: { value: '100' } });

      expect(onChange).toHaveBeenCalledWith('amount', 100);
    });

    it('textarea 字段输入触发 onChange', () => {
      const fields: FormField[] = [
        { key: 'reason', label: '原因', type: 'textarea' },
      ];
      const { onChange } = renderForm(fields);

      const textarea = screen.getByPlaceholderText('请输入原因');
      fireEvent.change(textarea, { target: { value: '请假原因' } });

      expect(onChange).toHaveBeenCalledWith('reason', '请假原因');
    });

    it('multiselect 字段点击触发 onChange', () => {
      const fields: FormField[] = [
        { key: 'skills', label: '技能', type: 'multiselect', options: ['React', 'Vue'] },
      ];
      const { onChange } = renderForm(fields);

      // 点击 React checkbox
      const reactCheckbox = screen.getByText('React');
      fireEvent.click(reactCheckbox);

      expect(onChange).toHaveBeenCalledWith('skills', ['React']);
    });
  });

  describe('description 帮助文本', () => {
    it('渲染字段描述', () => {
      const fields: FormField[] = [
        { key: 'amount', label: '金额', type: 'number', description: '请输入报销金额（元）' },
      ];
      renderForm(fields);

      expect(screen.getByText('请输入报销金额（元）')).toBeInTheDocument();
    });
  });
});
