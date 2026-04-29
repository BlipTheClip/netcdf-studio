import { useProcessorStore } from "@/store/processorStore";
import { Select } from "@/components/Select";

interface VariableSelectorProps {
  value: string;
  onChange: (variable: string) => void;
}

/** Dropdown populated from the currently loaded file's variables. */
export function VariableSelector({ value, onChange }: VariableSelectorProps) {
  const { metadata } = useProcessorStore();
  if (!metadata) return null;

  const options = Object.values(metadata.variables).map((v) => ({
    value: v.name,
    label: v.units ? `${v.name}  [${v.units}]` : v.name,
  }));

  return (
    <Select
      label="Variable"
      options={options}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
