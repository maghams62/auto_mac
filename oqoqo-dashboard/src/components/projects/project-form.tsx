"use client";

import { useFieldArray, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { Project, ProjectDraft, RepoConfig } from "@/lib/types";

const repoSchema = z.object({
  id: z.string().optional(),
  name: z.string().min(2, "Name is required"),
  repoUrl: z.string().url("Provide a valid repo URL"),
  branch: z.string().min(1, "Branch is required"),
  serviceType: z.string().min(2, "Service type is required"),
  docLocations: z.string().min(1, "At least one doc path"),
  labels: z.string().optional(),
  linearProject: z.string().optional(),
  jiraProject: z.string().optional(),
  slackChannels: z.string().optional(),
  supportTags: z.string().optional(),
});

const projectSchema = z.object({
  name: z.string().min(3, "Project name is required"),
  description: z.string().min(10, "Describe the project"),
  horizon: z.enum(["prod", "staging"]),
  tags: z.string().optional(),
  repos: z.array(repoSchema).min(1, "Define at least one repo/source"),
});

type ProjectFormValues = z.infer<typeof projectSchema>;

const defaultRepoRow = {
  name: "",
  repoUrl: "",
  branch: "main",
  serviceType: "Service",
  docLocations: "docs",
  labels: "",
  linearProject: "",
  jiraProject: "",
  slackChannels: "",
  supportTags: "",
};

const toFormValues = (project?: Project): ProjectFormValues => {
  if (!project) {
    return {
      name: "",
      description: "",
      horizon: "prod",
      tags: "",
      repos: [{ ...defaultRepoRow }],
    };
  }

  return {
    name: project.name,
    description: project.description,
    horizon: project.horizon,
    tags: project.tags.join(", "),
    repos: project.repos.map((repo) => ({
      id: repo.id,
      name: repo.name,
      repoUrl: repo.repoUrl,
      branch: repo.branch,
      serviceType: repo.serviceType,
      docLocations: repo.docLocations.join(", "),
      labels: repo.labels.join(", "),
      linearProject: repo.linkedSystems.linearProject ?? "",
      jiraProject: repo.linkedSystems.jiraProject ?? "",
      slackChannels: (repo.linkedSystems.slackChannels ?? []).join(", "),
      supportTags: (repo.linkedSystems.supportTags ?? []).join(", "),
    })),
  };
};

const splitList = (value?: string) =>
  value
    ?.split(",")
    .map((item) => item.trim())
    .filter(Boolean) ?? [];

interface ProjectFormProps {
  project?: Project;
  onSubmit: (draft: ProjectDraft) => Promise<void> | void;
  submitLabel?: string;
}

export function ProjectForm({ project, onSubmit, submitLabel = "Save project" }: ProjectFormProps) {
  const form = useForm<ProjectFormValues>({
    resolver: zodResolver(projectSchema),
    defaultValues: toFormValues(project),
  });

  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: "repos",
  });

  const handleSubmit = form.handleSubmit(async (values) => {
    const draft: ProjectDraft = {
      id: project?.id,
      name: values.name,
      description: values.description,
      horizon: values.horizon,
      tags: splitList(values.tags),
      repos: values.repos.map((repo) => ({
        id: repo.id ?? `repo_${Math.random().toString(36).slice(2, 8)}`,
        name: repo.name,
        repoUrl: repo.repoUrl,
        branch: repo.branch,
        serviceType: repo.serviceType,
        labels: splitList(repo.labels),
        docLocations: splitList(repo.docLocations),
        linkedSystems: {
          linearProject: repo.linearProject || undefined,
          jiraProject: repo.jiraProject || undefined,
          slackChannels: splitList(repo.slackChannels),
          supportTags: splitList(repo.supportTags),
        },
      })) as RepoConfig[],
    };

    await onSubmit(draft);
    if (!project) {
      form.reset(toFormValues());
    }
  });

  return (
    <Form {...form}>
      <form className="space-y-6" onSubmit={handleSubmit}>
        <div className="grid gap-4 md:grid-cols-2">
          <FormField
            control={form.control}
            name="name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Project name</FormLabel>
                <FormControl>
                  <Input placeholder="Atlas Activity Graph" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="horizon"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Monitoring horizon</FormLabel>
                <FormControl>
                  <Input placeholder="prod | staging" {...field} />
                </FormControl>
                <FormDescription>Use prod for critical customer flows.</FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description</FormLabel>
              <FormControl>
                <Textarea rows={3} placeholder="What does this project monitor?" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="tags"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Tags</FormLabel>
              <FormControl>
                <Input placeholder="payments, drift, critical" {...field} />
              </FormControl>
              <FormDescription>Comma separated labels for grouping.</FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="space-y-4 rounded-2xl border border-border/60 p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold">Repositories & services</div>
              <p className="text-xs text-muted-foreground">Define all repos, branches, and doc paths to monitor.</p>
            </div>
            <Button
              type="button"
              variant="outline"
              className="rounded-full text-xs"
              onClick={() => append({ ...defaultRepoRow })}
            >
              <Plus className="mr-2 h-4 w-4" />
              Add repo
            </Button>
          </div>

          <div className="space-y-6">
            {fields.map((field, index) => (
              <div key={field.id} className="rounded-2xl border border-border/40 p-4">
                <div className="mb-4 flex items-center justify-between">
                  <div className="text-sm font-semibold text-muted-foreground">Repo #{index + 1}</div>
                  {fields.length > 1 && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="text-destructive"
                      onClick={() => remove(index)}
                    >
                      <Trash2 className="mr-1 h-4 w-4" />
                      Remove
                    </Button>
                  )}
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <FormField
                    control={form.control}
                    name={`repos.${index}.name`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Repo name</FormLabel>
                        <FormControl>
                          <Input placeholder="atlas-core-api" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name={`repos.${index}.branch`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Branch</FormLabel>
                        <FormControl>
                          <Input placeholder="main" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name={`repos.${index}.repoUrl`}
                    render={({ field }) => (
                      <FormItem className="md:col-span-2">
                        <FormLabel>Repository URL</FormLabel>
                        <FormControl>
                          <Input placeholder="https://github.com/oqoqo/atlas-core-api" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name={`repos.${index}.serviceType`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Service type</FormLabel>
                        <FormControl>
                          <Input placeholder="API Gateway, Shared Library, etc." {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name={`repos.${index}.docLocations`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Doc locations</FormLabel>
                        <FormControl>
                          <Input placeholder="docs/api, docs/runbooks" {...field} />
                        </FormControl>
                        <FormDescription>Comma separated directories/files.</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name={`repos.${index}.labels`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Labels</FormLabel>
                        <FormControl>
                          <Input placeholder="payments, customer-facing" {...field} />
                        </FormControl>
                        <FormDescription>Comma separated descriptors.</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name={`repos.${index}.linearProject`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Linear project key</FormLabel>
                        <FormControl>
                          <Input placeholder="ATLAS" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name={`repos.${index}.jiraProject`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Jira project key</FormLabel>
                        <FormControl>
                          <Input placeholder="AUTH" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name={`repos.${index}.slackChannels`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Slack channels</FormLabel>
                        <FormControl>
                          <Input placeholder="#atlas-drifts, #support-handoff" {...field} />
                        </FormControl>
                        <FormDescription>Comma separated channel names.</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name={`repos.${index}.supportTags`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Support tags</FormLabel>
                        <FormControl>
                          <Input placeholder="atlas-core, api-regression" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="flex justify-end">
          <Button type="submit" className="rounded-full px-6">
            {submitLabel}
          </Button>
        </div>
      </form>
    </Form>
  );
}

