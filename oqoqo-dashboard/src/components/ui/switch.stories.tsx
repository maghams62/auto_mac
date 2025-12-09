import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";

import { Switch } from "./switch";

const meta: Meta<typeof Switch> = {
  title: "UI/Switch",
  component: Switch,
  args: {
    label: "Slack hints",
    checked: true,
  },
};

export default meta;

type Story = StoryObj<typeof Switch>;

export const Controlled: Story = {
  render: (args) => {
    const [checked, setChecked] = useState(args.checked ?? false);
    return (
      <Switch
        {...args}
        checked={checked}
        onCheckedChange={(value) => {
          setChecked(value);
          args.onCheckedChange?.(value);
        }}
      />
    );
  },
};


