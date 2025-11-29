"use client";

import * as React from "react";
import { Controller, FormProvider, useFormContext } from "react-hook-form";

import { cn } from "@/lib/utils";

type FormErrorRecord = Record<string, { message?: string }>;

const Form = FormProvider;

const FormField = Controller;

interface FormItemContextValue {
  id: string;
}

const FormItemContext = React.createContext<FormItemContextValue>({ id: "" });

const FormItem = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({ className, ...props }, ref) => {
  const id = React.useId();

  return (
    <FormItemContext.Provider value={{ id }}>
      <div ref={ref} className={cn("space-y-2", className)} {...props} />
    </FormItemContext.Provider>
  );
});
FormItem.displayName = "FormItem";

const FormLabel = React.forwardRef<
  React.ElementRef<"label">,
  React.LabelHTMLAttributes<HTMLLabelElement>
>(({ className, ...props }, ref) => {
  const { id } = React.useContext(FormItemContext);
  return <label ref={ref} className={cn("text-sm font-medium text-muted-foreground", className)} htmlFor={id} {...props} />;
});
FormLabel.displayName = "FormLabel";

const FormControl = React.forwardRef<
  React.ElementRef<"div">,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => {
  const { id } = React.useContext(FormItemContext);

  return <div ref={ref} className={cn("space-y-2", className)} data-id={id} {...props} />;
});
FormControl.displayName = "FormControl";

const FormDescription = React.forwardRef<
  React.ElementRef<"p">,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p ref={ref} className={cn("text-xs text-muted-foreground/80", className)} {...props} />
));
FormDescription.displayName = "FormDescription";

const FormMessage = React.forwardRef<
  React.ElementRef<"p">,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, children, ...props }, ref) => {
  const { formState } = useFormContext();
  const id = React.useContext(FormItemContext).id;
  const error = id ? (formState.errors as FormErrorRecord)[id]?.message : undefined;

  return (
    <p ref={ref} className={cn("text-xs font-medium text-destructive", className)} {...props}>
      {error ? String(error) : children}
    </p>
  );
});
FormMessage.displayName = "FormMessage";

export { Form, FormField, FormItem, FormLabel, FormControl, FormDescription, FormMessage };

