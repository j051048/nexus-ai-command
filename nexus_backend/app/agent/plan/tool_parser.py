"""[K] Tool call parsing + schema validation."""

from app.agent.node_helpers import (
    AgentConfig,
    AgentPhase,
    QueryComplexity,
    ThinkingStep,
    ToolCallRecord,
    _format_validation_error,
    _try_extract_tool_names,
    get_tool,
    logger,
)


def parse_tool_calls(
    tool_calls_raw: list,
    *,
    content: str,
    agent_config: AgentConfig,
    iteration: int,
    state: dict,
    input_tokens: int,
    output_tokens: int,
    thinking_step: ThinkingStep,
):
    """Parse raw tool calls, validate schemas, handle Gemini concatenation bugs.

    Returns (pending_tools, validation_error_result_or_None).
    If validation_error_result is not None, the caller should return it immediately.
    """
    pending_tools: list[ToolCallRecord] = []
    validation_errors: list[str] = []

    if not tool_calls_raw:
        return pending_tools, None

    for tc in tool_calls_raw:
        tc_name = tc.get("name", "unknown")
        tc_args = tc.get("args", {})
        tc_id = tc.get("id", "")

        # Gemini concatenation bug: split concatenated tool names into separate records
        if not get_tool(tc_name):
            extracted = _try_extract_tool_names(tc_name)
            if extracted:
                logger.warning(
                    f"[PlanNode] Splitting concatenated tool name '{tc_name}' "
                    f"into {len(extracted)} tools: {extracted}"
                )
                for i, ename in enumerate(extracted):
                    if i == 0:
                        pending_tools.append(
                            ToolCallRecord(
                                tool_name=ename,
                                tool_args=tc_args,
                                tool_call_id=f"{tc_id}_split{i}" if tc_id else "",
                            )
                        )
                    else:
                        split_tool = get_tool(ename)
                        if (
                            split_tool
                            and hasattr(split_tool, "parameters")
                            and split_tool.parameters
                        ):
                            required = set(
                                split_tool.parameters.get("required", [])
                            )
                            all_props = set(
                                split_tool.parameters.get("properties", {}).keys()
                            )
                            split_args = {
                                k: v for k, v in tc_args.items() if k in all_props
                            }
                            if required and required.issubset(split_args.keys()):
                                pending_tools.append(
                                    ToolCallRecord(
                                        tool_name=ename,
                                        tool_args=split_args,
                                        tool_call_id=(
                                            f"{tc_id}_split{i}" if tc_id else ""
                                        ),
                                    )
                                )
                            else:
                                logger.warning(
                                    "[PlanNode] Skipping split tool '%s': "
                                    "required args %s not found in available %s",
                                    ename,
                                    required,
                                    set(tc_args.keys()),
                                )
                        else:
                            logger.warning(
                                "[PlanNode] Skipping split tool '%s': tool not found or no schema",
                                ename,
                            )
                continue

        # Pre-execution schema validation: catch bad args before execute_node
        tool_obj = get_tool(tc_name)
        if tool_obj and tool_obj.parameters and tc_args:
            try:
                import jsonschema

                jsonschema.validate(instance=tc_args, schema=tool_obj.parameters)
            except Exception as ve:
                error_msg = _format_validation_error(
                    tc_name, ve, tool_obj.parameters
                )
                validation_errors.append(error_msg)
                logger.warning(
                    f"[PlanNode] Pre-exec validation failed for {tc_name}: {ve}"
                )
                # Still add to pending — execute_node will catch it too,
                # but we collect errors to give LLM a chance to self-correct
                pending_tools.append(
                    ToolCallRecord(
                        tool_name=tc_name,
                        tool_args=tc_args,
                        tool_call_id=tc_id,
                    )
                )
                continue

        pending_tools.append(
            ToolCallRecord(
                tool_name=tc_name,
                tool_args=tc_args,
                tool_call_id=tc_id,
            )
        )

    # If validation errors were found, inject guidance into next iteration
    if validation_errors and iteration < (agent_config.max_iterations - 1):
        error_feedback = "\n\n".join(validation_errors)
        logger.info(
            f"[PlanNode] {len(validation_errors)} tool arg validation errors, requesting LLM correction"
        )
        from langchain_core.messages import AIMessage as _AIMessage

        correction_msg = _AIMessage(
            content=f"[参数校验错误] 以下工具调用参数不符合要求，请修正后重试：\n\n{error_feedback}"
        )
        return pending_tools, {
            "messages": [correction_msg],
            "current_phase": AgentPhase.PLANNING,
            "plan": content or "(参数校验失败，需修正)",
            "requires_tools": False,
            "pending_tool_calls": [],
            "thinking_steps": [
                thinking_step,
                ThinkingStep(
                    phase=AgentPhase.PLANNING.value,
                    content=f"工具参数校验失败 ({len(validation_errors)} 个错误)，请求 LLM 修正参数",
                ),
            ],
            "reflection_guidance": f"工具参数校验失败，请修正以下问题：\n{error_feedback}",
            "needs_replanning": True,
            "iteration": iteration + 1,
            "total_input_tokens": state.get("total_input_tokens", 0) + input_tokens,
            "total_output_tokens": state.get("total_output_tokens", 0) + output_tokens,
        }

    return pending_tools, None
