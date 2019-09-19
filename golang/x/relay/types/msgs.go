package types

import (
	"encoding/hex"

	sdk "github.com/cosmos/cosmos-sdk/types"
)

// RouterKey is a name for the router
const RouterKey = ModuleName // this was defined in your key.go file

// MsgSetLink defines a SetLink message
type MsgSetLink struct {
	Header string `json:"header"`
}

// NewMsgSetLink is a constructor function for MsgSetLink
func NewMsgSetLink(header string, owner sdk.AccAddress) MsgSetLink {
	return MsgSetLink{
		Header: header,
	}
}

// Route should return the name of the module
func (msg MsgSetLink) Route() string { return RouterKey }

// Type should return the action
func (msg MsgSetLink) Type() string { return "set_link" }

// ValidateBasic runs stateless checks on the message
func (msg MsgSetLink) ValidateBasic() sdk.Error {
	b, err := hex.DecodeString(msg.Header)
	if err != nil || len(b) != 80 {
		return ErrBadHeaderLength(DefaultCodespace)
	}
	return nil
}

// GetSignBytes encodes the message for signing
func (msg MsgSetLink) GetSignBytes() []byte {
	return sdk.MustSortJSON(ModuleCdc.MustMarshalJSON(msg))
}

// GetSigners defines whose signature is required
func (msg MsgSetLink) GetSigners() []sdk.AccAddress {
	return []sdk.AccAddress{}
}