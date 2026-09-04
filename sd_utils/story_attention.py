"""
story_attention.py
Consistent Self-Attention processor cho StoryDiffusion SDXL.
Được copy và làm sạch từ StoryDiffusion/predict.py.
"""
import copy
import random
import torch
import torch.nn.functional as F
import torch.nn as nn


# ===== GLOBAL STATE (được set từ bên ngoài trước khi generate) =====
total_count: int = 0
attn_count: int = 0
cur_step: int = 0
mask1024 = None
mask4096 = None
write: bool = False
sa32: float = 0.5
sa64: float = 0.5
height: int = 768
width: int = 768


# ===== MASK HELPER (từ StoryDiffusion/utils/gradio_utils.py) =====
def cal_attn_mask_xl(total_length, id_length, sa32, sa64, height, width, device="cuda", dtype=torch.float16):
    nums_1024 = (height // 32) * (width // 32)
    nums_4096 = (height // 16) * (width // 16)
    bool_matrix1024 = torch.rand((1, total_length * nums_1024), device=device, dtype=dtype) < sa32
    bool_matrix4096 = torch.rand((1, total_length * nums_4096), device=device, dtype=dtype) < sa64
    bool_matrix1024 = bool_matrix1024.repeat(total_length, 1)
    bool_matrix4096 = bool_matrix4096.repeat(total_length, 1)
    for i in range(total_length):
        bool_matrix1024[i:i+1, id_length * nums_1024:] = False
        bool_matrix4096[i:i+1, id_length * nums_4096:] = False
        bool_matrix1024[i:i+1, i * nums_1024:(i+1) * nums_1024] = True
        bool_matrix4096[i:i+1, i * nums_4096:(i+1) * nums_4096] = True
    mask1024 = bool_matrix1024.unsqueeze(1).repeat(1, nums_1024, 1).reshape(-1, total_length * nums_1024)
    mask4096 = bool_matrix4096.unsqueeze(1).repeat(1, nums_4096, 1).reshape(-1, total_length * nums_4096)
    return mask1024, mask4096


# ===== DEFAULT ATTENTION PROCESSOR =====
class AttnProcessor(nn.Module):
    def __init__(self, hidden_size=None, cross_attention_dim=None):
        super().__init__()

    def __call__(self, attn, hidden_states, encoder_hidden_states=None, attention_mask=None, temb=None):
        residual = hidden_states
        if attn.spatial_norm is not None:
            hidden_states = attn.spatial_norm(hidden_states, temb)
        input_ndim = hidden_states.ndim
        if input_ndim == 4:
            batch_size, channel, height, width = hidden_states.shape
            hidden_states = hidden_states.view(batch_size, channel, height * width).transpose(1, 2)
        batch_size, sequence_length, _ = hidden_states.shape
        if attention_mask is not None:
            attention_mask = attn.prepare_attention_mask(attention_mask, sequence_length, batch_size)
            attention_mask = attention_mask.view(batch_size, attn.heads, -1, attention_mask.shape[-1])
        if attn.group_norm is not None:
            hidden_states = attn.group_norm(hidden_states.transpose(1, 2)).transpose(1, 2)
        query = attn.to_q(hidden_states)
        if encoder_hidden_states is None:
            encoder_hidden_states = hidden_states
        elif attn.norm_cross:
            encoder_hidden_states = attn.norm_encoder_hidden_states(encoder_hidden_states)
        key = attn.to_k(encoder_hidden_states)
        value = attn.to_v(encoder_hidden_states)
        inner_dim = key.shape[-1]
        head_dim = inner_dim // attn.heads
        query = query.view(batch_size, -1, attn.heads, head_dim).transpose(1, 2)
        key = key.view(batch_size, -1, attn.heads, head_dim).transpose(1, 2)
        value = value.view(batch_size, -1, attn.heads, head_dim).transpose(1, 2)
        hidden_states = F.scaled_dot_product_attention(query, key, value, attn_mask=attention_mask, dropout_p=0.0, is_causal=False)
        hidden_states = hidden_states.transpose(1, 2).reshape(batch_size, -1, attn.heads * head_dim)
        hidden_states = hidden_states.to(query.dtype)
        hidden_states = attn.to_out[0](hidden_states)
        hidden_states = attn.to_out[1](hidden_states)
        if input_ndim == 4:
            hidden_states = hidden_states.transpose(-1, -2).reshape(batch_size, channel, height, width)
        if attn.residual_connection:
            hidden_states = hidden_states + residual
        hidden_states = hidden_states / attn.rescale_output_factor
        return hidden_states


# ===== CONSISTENT SELF-ATTENTION PROCESSOR (từ predict.py) =====
class SpatialAttnProcessor2_0(torch.nn.Module):
    """
    Attention processor cho Consistent Self-Attention trong StoryDiffusion.
    Được lấy từ predict.py - dùng cal_attn_mask_xl (SDXL).
    Không dùng sa16/mask256 (đó là phiên bản cũ/SD1.5).
    """
    def __init__(self, hidden_size=None, cross_attention_dim=None, id_length=4, device="cuda", dtype=torch.float16):
        super().__init__()
        if not hasattr(F, "scaled_dot_product_attention"):
            raise ImportError("AttnProcessor2_0 requires PyTorch 2.0+")
        self.device = device
        self.dtype = dtype
        self.hidden_size = hidden_size
        self.cross_attention_dim = cross_attention_dim
        self.total_length = id_length + 1
        self.id_length = id_length
        self.id_bank = {}

    def __call__(self, attn, hidden_states, encoder_hidden_states=None, attention_mask=None, temb=None):
        import sd_utils.story_attention as sa_module
        if sa_module.write:
            sa_module.attn_count  # touch to ensure accessible
            self.id_bank[sa_module.cur_step] = [
                hidden_states[:self.id_length],
                hidden_states[self.id_length:],
            ]
        else:
            encoder_hidden_states = torch.cat((
                self.id_bank[sa_module.cur_step][0].to(self.device),
                hidden_states[:1],
                self.id_bank[sa_module.cur_step][1].to(self.device),
                hidden_states[1:],
            ))
        # Skip consistent attention in early steps
        if sa_module.cur_step < 5:
            hidden_states = self.__call2__(attn, hidden_states, encoder_hidden_states, attention_mask, temb)
        else:
            random_number = random.random()
            rand_num = 0.3 if sa_module.cur_step < 20 else 0.1
            if random_number > rand_num:
                if not sa_module.write:
                    if hidden_states.shape[1] == (sa_module.height // 32) * (sa_module.width // 32):
                        attention_mask = sa_module.mask1024[sa_module.mask1024.shape[0] // self.total_length * self.id_length:]
                    else:
                        attention_mask = sa_module.mask4096[sa_module.mask4096.shape[0] // self.total_length * self.id_length:]
                else:
                    if hidden_states.shape[1] == (sa_module.height // 32) * (sa_module.width // 32):
                        attention_mask = sa_module.mask1024[:sa_module.mask1024.shape[0] // self.total_length * self.id_length,
                                                             :sa_module.mask1024.shape[0] // self.total_length * self.id_length]
                    else:
                        attention_mask = sa_module.mask4096[:sa_module.mask4096.shape[0] // self.total_length * self.id_length,
                                                             :sa_module.mask4096.shape[0] // self.total_length * self.id_length]
                hidden_states = self.__call1__(attn, hidden_states, encoder_hidden_states, attention_mask, temb)
            else:
                hidden_states = self.__call2__(attn, hidden_states, None, attention_mask, temb)

        sa_module.attn_count += 1
        if sa_module.attn_count == sa_module.total_count:
            sa_module.attn_count = 0
            sa_module.cur_step += 1
            sa_module.mask1024, sa_module.mask4096 = cal_attn_mask_xl(
                self.total_length, self.id_length,
                sa_module.sa32, sa_module.sa64,
                sa_module.height, sa_module.width,
                device=self.device, dtype=self.dtype
            )
        return hidden_states

    def __call1__(self, attn, hidden_states, encoder_hidden_states=None, attention_mask=None, temb=None):
        residual = hidden_states
        if attn.spatial_norm is not None:
            hidden_states = attn.spatial_norm(hidden_states, temb)
        input_ndim = hidden_states.ndim
        if input_ndim == 4:
            total_batch_size, channel, height, width = hidden_states.shape
            hidden_states = hidden_states.view(total_batch_size, channel, height * width).transpose(1, 2)
        total_batch_size, nums_token, channel = hidden_states.shape
        img_nums = total_batch_size // 2
        hidden_states = hidden_states.view(-1, img_nums, nums_token, channel).reshape(-1, img_nums * nums_token, channel)
        batch_size, sequence_length, _ = hidden_states.shape
        if attn.group_norm is not None:
            hidden_states = attn.group_norm(hidden_states.transpose(1, 2)).transpose(1, 2)
        query = attn.to_q(hidden_states)
        if encoder_hidden_states is None:
            encoder_hidden_states = hidden_states
        else:
            encoder_hidden_states = encoder_hidden_states.view(-1, self.id_length + 1, nums_token, channel).reshape(-1, (self.id_length + 1) * nums_token, channel)
        key = attn.to_k(encoder_hidden_states)
        value = attn.to_v(encoder_hidden_states)
        inner_dim = key.shape[-1]
        head_dim = inner_dim // attn.heads
        query = query.view(batch_size, -1, attn.heads, head_dim).transpose(1, 2)
        key = key.view(batch_size, -1, attn.heads, head_dim).transpose(1, 2)
        value = value.view(batch_size, -1, attn.heads, head_dim).transpose(1, 2)
        hidden_states = F.scaled_dot_product_attention(query, key, value, attn_mask=attention_mask, dropout_p=0.0, is_causal=False)
        hidden_states = hidden_states.transpose(1, 2).reshape(total_batch_size, -1, attn.heads * head_dim)
        hidden_states = hidden_states.to(query.dtype)
        hidden_states = attn.to_out[0](hidden_states)
        hidden_states = attn.to_out[1](hidden_states)
        if input_ndim == 4:
            hidden_states = hidden_states.transpose(-1, -2).reshape(total_batch_size, channel, height, width)
        if attn.residual_connection:
            hidden_states = hidden_states + residual
        hidden_states = hidden_states / attn.rescale_output_factor
        return hidden_states

    def __call2__(self, attn, hidden_states, encoder_hidden_states=None, attention_mask=None, temb=None):
        residual = hidden_states
        if attn.spatial_norm is not None:
            hidden_states = attn.spatial_norm(hidden_states, temb)
        input_ndim = hidden_states.ndim
        if input_ndim == 4:
            batch_size, channel, height, width = hidden_states.shape
            hidden_states = hidden_states.view(batch_size, channel, height * width).transpose(1, 2)
        batch_size, sequence_length, channel = hidden_states.shape
        if attention_mask is not None:
            attention_mask = attn.prepare_attention_mask(attention_mask, sequence_length, batch_size)
            attention_mask = attention_mask.view(batch_size, attn.heads, -1, attention_mask.shape[-1])
        if attn.group_norm is not None:
            hidden_states = attn.group_norm(hidden_states.transpose(1, 2)).transpose(1, 2)
        query = attn.to_q(hidden_states)
        if encoder_hidden_states is None:
            encoder_hidden_states = hidden_states
        else:
            encoder_hidden_states = encoder_hidden_states.view(-1, self.id_length + 1, sequence_length, channel).reshape(-1, (self.id_length + 1) * sequence_length, channel)
        key = attn.to_k(encoder_hidden_states)
        value = attn.to_v(encoder_hidden_states)
        inner_dim = key.shape[-1]
        head_dim = inner_dim // attn.heads
        query = query.view(batch_size, -1, attn.heads, head_dim).transpose(1, 2)
        key = key.view(batch_size, -1, attn.heads, head_dim).transpose(1, 2)
        value = value.view(batch_size, -1, attn.heads, head_dim).transpose(1, 2)
        hidden_states = F.scaled_dot_product_attention(query, key, value, attn_mask=attention_mask, dropout_p=0.0, is_causal=False)
        hidden_states = hidden_states.transpose(1, 2).reshape(batch_size, -1, attn.heads * head_dim)
        hidden_states = hidden_states.to(query.dtype)
        hidden_states = attn.to_out[0](hidden_states)
        hidden_states = attn.to_out[1](hidden_states)
        if input_ndim == 4:
            hidden_states = hidden_states.transpose(-1, -2).reshape(batch_size, channel, height, width)
        if attn.residual_connection:
            hidden_states = hidden_states + residual
        hidden_states = hidden_states / attn.rescale_output_factor
        return hidden_states


# ===== SETUP FUNCTION =====
def set_attention_processor(unet, id_length, is_ipadapter=False):
    """Inject SpatialAttnProcessor2_0 vào tất cả up_blocks của UNet."""
    import sd_utils.story_attention as sa_module
    sa_module.total_count = 0
    attn_procs = {}
    for name in unet.attn_processors.keys():
        cross_attention_dim = None if name.endswith("attn1.processor") else unet.config.cross_attention_dim
        if cross_attention_dim is None:
            if name.startswith("up_blocks"):
                attn_procs[name] = SpatialAttnProcessor2_0(id_length=id_length)
                sa_module.total_count += 1
            else:
                attn_procs[name] = AttnProcessor()
        else:
            attn_procs[name] = AttnProcessor()
    unet.set_attn_processor(copy.deepcopy(attn_procs))
    print(f"✅ Đã inject SpatialAttnProcessor vào {sa_module.total_count} up_blocks.")


def setup_storydiffusion_state(pipe, id_length=3, sa32=0.5, sa64=0.5, height=768, width=768):
    """Khởi tạo toàn bộ global state cho một lần generate."""
    import sd_utils.story_attention as sa_module
    device = next(pipe.unet.parameters()).device
    dtype = next(pipe.unet.parameters()).dtype

    set_attention_processor(pipe.unet, id_length)

    sa_module.sa32 = sa32
    sa_module.sa64 = sa64
    sa_module.height = height
    sa_module.width = width
    sa_module.write = False
    sa_module.attn_count = 0
    sa_module.cur_step = 0

    sa_module.mask1024, sa_module.mask4096 = cal_attn_mask_xl(
        id_length + 1, id_length, sa32, sa64, height, width,
        device=str(device), dtype=dtype
    )
    print(f"✅ Khởi tạo StoryDiffusion xong! (id_length={id_length}, {height}x{width})")
