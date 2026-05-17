import { render, screen } from "@testing-library/react";
import ChatMessage from "../ChatMessage";

describe("ChatMessage", () => {
  it("renders text content", () => {
    render(
      <ChatMessage
        agentName="谋略家"
        content="这是一条消息"
        createdAt="2025-01-01T12:00:00Z"
      />
    );
    expect(screen.getByText("谋略家")).toBeInTheDocument();
    expect(screen.getByText("这是一条消息")).toBeInTheDocument();
  });

  it("renders system message", () => {
    render(
      <ChatMessage
        content="系统消息"
        createdAt="2025-01-01T12:00:00Z"
        isSystem
      />
    );
    expect(screen.getByText("系统消息")).toBeInTheDocument();
  });

  it("renders image content", () => {
    render(
      <ChatMessage
        agentName="创意大师"
        content=""
        contentType="image"
        imageUrl="https://example.com/image.png"
        createdAt="2025-01-01T12:00:00Z"
      />
    );
    const img = screen.getByAltText("生成的图片");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", "https://example.com/image.png");
  });

  it("renders audio content", () => {
    render(
      <ChatMessage
        agentName="配音师"
        content=""
        contentType="audio"
        audioUrl="https://example.com/audio.mp3"
        createdAt="2025-01-01T12:00:00Z"
      />
    );
    const audio = document.querySelector("audio");
    expect(audio).toBeInTheDocument();
  });

  it("renders unknown agent when no name", () => {
    render(
      <ChatMessage
        content="匿名消息"
        createdAt="2025-01-01T12:00:00Z"
      />
    );
    expect(screen.getByText("未知")).toBeInTheDocument();
  });
});
